import os
from datetime import timedelta
from modulos_agenda import listar_subetapas_projeto
from modulos_calendario import converter_data, gerar_dias_uteis
from modulos_geral import pasta_do_app, limpar_terminal

try:
    import openpyxl
    from openpyxl.chart import BarChart, LineChart, Reference
    from openpyxl.styles import Alignment, Font, PatternFill

    EXCEL_DISPONIVEL = True
except ImportError:
    EXCEL_DISPONIVEL = False

DIRETORIO_ATUAL = pasta_do_app()
SEMANAS_POR_BLOCO = 8  # colunas de semana por bloco na tela


# ==============================================================================
# 1. CÁLCULOS: HISTOGRAMA SEMANAL E CURVA S
# ==============================================================================

def inicio_da_semana(dia):
    """Segunda-feira da semana da data informada."""
    return dia - timedelta(days=dia.weekday())


def pessoas_da_subetapa(sub):
    """Efetivo diário da subetapa por profissão (equipe básica x nº de equipes)."""
    n_eqp = sub.get("quantidade_equipes", 1)
    return {prof: qtd * n_eqp for prof, qtd in sub.get("equipe_basica", {}).items()}


def calcular_histograma(projeto_obj, obras, cron, resumo):
    """
    Efetivo previsto por semana e profissão, a partir do cronograma calculado.

    Retorna (semanas, profissoes, pico, hh): pico[prof][semana] = maior efetivo diário
    na semana; hh[prof][semana] = homens-hora da semana. A profissão 'TOTAL' traz o
    pico do efetivo somado de todas as profissões no mesmo dia.
    """
    horas_dia = resumo["calendario"]["horas_dia"]
    dias = gerar_dias_uteis(resumo["data_inicio"], resumo["duracao"] + 1, resumo["calendario"])

    efetivo_dia = {}  # índice do dia útil -> {profissão: pessoas}
    for tid, t in listar_subetapas_projeto(obras, projeto_obj["nome"]).items():
        c = cron[tid]
        for d in range(c["es"], c["ef"]):
            dia = efetivo_dia.setdefault(d, {})
            for prof, qtd in pessoas_da_subetapa(t["sub"]).items():
                dia[prof] = dia.get(prof, 0) + qtd

    semanas = sorted({inicio_da_semana(dias[d]) for d in range(resumo["duracao"])})
    profissoes = sorted({p for dia in efetivo_dia.values() for p in dia})
    pico = {p: {s: 0 for s in semanas} for p in profissoes + ["TOTAL"]}
    hh = {p: {s: 0.0 for s in semanas} for p in profissoes + ["TOTAL"]}

    for d, por_prof in efetivo_dia.items():
        semana = inicio_da_semana(dias[d])
        for prof, qtd in por_prof.items():
            pico[prof][semana] = max(pico[prof][semana], qtd)
            hh[prof][semana] += qtd * horas_dia
            hh["TOTAL"][semana] += qtd * horas_dia
        pico["TOTAL"][semana] = max(pico["TOTAL"][semana], sum(por_prof.values()))

    return semanas, profissoes, pico, hh


def acumulado_ate(sub, data_limite):
    """Quantidade acumulada da última medição DATADA até a data limite (inclusive)."""
    valores = [m["acumulado"] for m in sub.get("medicoes", [])
               if m["data"] and m["data"] <= data_limite.isoformat()]
    return valores[-1] if valores else 0.0


def calcular_curva_s(projeto_obj, obras, cron, resumo):
    """
    Curva S semanal (avanço físico ponderado em HH), previsto x realizado.

    - Previsto: o HH de cada subetapa é distribuído igualmente pelos seus dias úteis.
    - Realizado: na data de fim de cada semana, usa a última medição datada de cada subetapa.
      Medições 'sem data' não entram na curva (são informadas à parte).
    Retorna (linhas, info), com linhas = [(fim_da_semana, previsto, realizado ou None)].
    """
    horas_dia = resumo["calendario"]["horas_dia"]
    tarefas = listar_subetapas_projeto(obras, projeto_obj["nome"])
    dias = gerar_dias_uteis(resumo["data_inicio"], resumo["duracao"] + 1, resumo["calendario"])

    hh_tarefa = {}
    for tid, t in tarefas.items():
        # Peso pelo HH PLANEJADO (igual ao memorial); a duração efetiva só distribui esse HH no tempo
        hh_tarefa[tid] = (cron[tid].get("duracao_planejada", cron[tid]["duracao"]) * horas_dia
                          * sum(pessoas_da_subetapa(t["sub"]).values()))
    hh_total = sum(hh_tarefa.values())

    datas_medicao = [converter_data(m["data"]) for t in tarefas.values()
                     for m in t["sub"].get("medicoes", []) if m["data"]]
    ultima_medicao = max(datas_medicao, default=None)

    fim_previsto = dias[max(0, resumo["duracao"] - 1)]
    ultima_data = max(fim_previsto, ultima_medicao) if ultima_medicao else fim_previsto
    semana = inicio_da_semana(resumo["data_inicio"])

    # HH previsto acumulado por dia útil
    hh_previsto_dia = {}
    for tid, c in cron.items():
        if c["duracao"]:
            por_dia = hh_tarefa[tid] / c["duracao"]
            for d in range(c["es"], c["ef"]):
                hh_previsto_dia[dias[d]] = hh_previsto_dia.get(dias[d], 0.0) + por_dia

    # Ponto de partida da curva: 0% na véspera do início da primeira semana
    linhas = [(semana - timedelta(days=1), 0.0, 0.0 if ultima_medicao else None)]
    while semana <= ultima_data:
        fim_semana = semana + timedelta(days=6)
        previsto = sum(v for dia, v in hh_previsto_dia.items() if dia <= fim_semana)
        realizado = None
        if ultima_medicao and semana <= ultima_medicao:
            realizado = 0.0
            for tid, t in tarefas.items():
                qtd = t["sub"].get("quantidade_fisica", 0.0)
                if qtd > 0:
                    realizado += hh_tarefa[tid] * min(1.0, acumulado_ate(t["sub"], fim_semana) / qtd)
        linhas.append((
            fim_semana,
            previsto / hh_total if hh_total else 0.0,
            (realizado / hh_total if hh_total else 0.0) if realizado is not None else None,
        ))
        semana += timedelta(days=7)

    # Parcela do avanço atual que vem de medições sem data (fica fora da curva)
    hh_sem_data = 0.0
    for tid, t in tarefas.items():
        qtd = t["sub"].get("quantidade_fisica", 0.0)
        sem_data = [m["acumulado"] for m in t["sub"].get("medicoes", []) if m["data"] is None]
        datadas = [m for m in t["sub"].get("medicoes", []) if m["data"]]
        if qtd > 0 and sem_data and not datadas:
            hh_sem_data += hh_tarefa[tid] * min(1.0, sem_data[-1] / qtd)

    info = {
        "hh_total": hh_total,
        "ultima_medicao": ultima_medicao,
        "pct_sem_data": hh_sem_data / hh_total if hh_total else 0.0,
    }
    return linhas, info


# ==============================================================================
# 2. VISUALIZAÇÃO NO TERMINAL
# ==============================================================================

def visualizar_histograma_curva_s(projeto_obj, obras, cron, resumo):
    """Exibe o histograma semanal de mão de obra e a curva S previsto x realizado."""
    semanas, profissoes, pico, hh = calcular_histograma(projeto_obj, obras, cron, resumo)
    linhas, info = calcular_curva_s(projeto_obj, obras, cron, resumo)

    limpar_terminal()
    print("=" * 100)
    print(f"HISTOGRAMA DE MÃO DE OBRA (EFETIVO PREVISTO) - {projeto_obj['nome'].upper()}")
    print("Valor = pico de pessoas em um mesmo dia da semana (semana iniciando na data indicada)")
    print("=" * 100)

    if not profissoes:
        print("  └── (Nenhuma subetapa com equipe básica cadastrada)")
    for ini in range(0, len(semanas), SEMANAS_POR_BLOCO):
        bloco = semanas[ini:ini + SEMANAS_POR_BLOCO]
        print(f"\n{'PROFISSÃO':<22}" + "".join(f"{s:%d/%m/%y}".rjust(10) for s in bloco))
        print("-" * (22 + 10 * len(bloco)))
        for prof in profissoes + ["TOTAL"]:
            print(f"{prof[:21]:<22}" + "".join(f"{pico[prof][s]:>10}" for s in bloco))
        print(f"{'HH TOTAL DA SEMANA':<22}" + "".join(f"{hh['TOTAL'][s]:>10.0f}" for s in bloco))

    print("\n" + "=" * 100)
    print("CURVA S - AVANÇO FÍSICO ACUMULADO (PONDERADO EM HH)")
    print("=" * 100)
    print(f"{'FIM DA SEMANA':<14} | {'PREVISTO':>8} | {'REALIZADO':>9} | {'DESVIO':>7} | PREVISTO (#) x REALIZADO (o)")
    print("-" * 100)
    for fim, prev, real in linhas:
        barra = ["·"] * 40
        barra[min(39, round(prev * 39))] = "#"
        if real is not None:
            pos = min(39, round(real * 39))
            barra[pos] = "o" if barra[pos] != "#" else "@"
        txt_real = f"{real * 100:>8.1f}%" if real is not None else f"{'-':>9}"
        txt_desv = f"{(real - prev) * 100:>+6.1f}%" if real is not None else f"{'':>7}"
        print(f"{fim:%d/%m/%Y}     | {prev * 100:>7.1f}% | {txt_real} | {txt_desv} | {''.join(barra)}")

    print("-" * 100)
    print("@ = previsto e realizado no mesmo ponto")
    if info["ultima_medicao"]:
        print(f"Última medição datada: {info['ultima_medicao']:%d/%m/%Y}")
    else:
        print("Nenhuma medição datada lançada: a linha do realizado ficará vazia.")
    if info["pct_sem_data"] > 0:
        print(f"⚠️ {info['pct_sem_data'] * 100:.1f}% de avanço vem de medições SEM DATA e não aparece na curva "
              "(informe a data na tela de medição).")
    input("\nPressione Enter para continuar...")


# ==============================================================================
# 3. EXPORTAÇÃO EXCEL (HISTOGRAMA + CURVA S COM GRÁFICOS)
# ==============================================================================

def exportar_histograma_curva_s_excel(projeto_obj, obras, cron, resumo):
    """Gera um .xlsx com as abas Histograma e Curva_S, cada uma com seu gráfico."""
    if not EXCEL_DISPONIVEL:
        print("\n❌ A biblioteca 'openpyxl' não está instalada. Instale via terminal: pip install openpyxl")
        return None

    semanas, profissoes, pico, hh = calcular_histograma(projeto_obj, obras, cron, resumo)
    linhas, info = calcular_curva_s(projeto_obj, obras, cron, resumo)

    fonte_head = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill_head = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    wb = openpyxl.Workbook()

    # --- Aba Histograma: semanas nas linhas, profissões nas colunas (formato do gráfico empilhado) ---
    ws = wb.active
    ws.title = "Histograma"
    ws.append(["SEMANA (INÍCIO)"] + profissoes + ["TOTAL (PICO DIÁRIO)", "HH DA SEMANA"])
    for s in semanas:
        ws.append([s] + [pico[p][s] for p in profissoes] + [pico["TOTAL"][s], round(hh["TOTAL"][s], 1)])
        ws.cell(row=ws.max_row, column=1).number_format = "DD/MM/YYYY"
    for cell in ws[1]:
        cell.font, cell.fill = fonte_head, fill_head
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.column_dimensions["A"].width = 16

    if profissoes and semanas:
        grafico = BarChart()
        grafico.type, grafico.grouping, grafico.overlap = "col", "stacked", 100
        grafico.title = "Histograma de Mão de Obra (pico de pessoas por semana)"
        grafico.y_axis.title, grafico.x_axis.title = "Pessoas", "Semana"
        grafico.add_data(Reference(ws, min_col=2, max_col=1 + len(profissoes), min_row=1, max_row=1 + len(semanas)),
                         titles_from_data=True)
        grafico.set_categories(Reference(ws, min_col=1, min_row=2, max_row=1 + len(semanas)))
        grafico.height, grafico.width = 10, 24
        ws.add_chart(grafico, f"A{len(semanas) + 4}")

    # --- Aba Curva S ---
    ws2 = wb.create_sheet("Curva_S")
    ws2.append(["FIM DA SEMANA", "PREVISTO ACUMULADO", "REALIZADO ACUMULADO", "DESVIO"])
    for fim, prev, real in linhas:
        ws2.append([fim, prev, real, (real - prev) if real is not None else None])
        linha = ws2.max_row
        ws2.cell(row=linha, column=1).number_format = "DD/MM/YYYY"
        for col in (2, 3, 4):
            ws2.cell(row=linha, column=col).number_format = "0.0%"
    for cell in ws2[1]:
        cell.font, cell.fill = fonte_head, fill_head
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    for col in "ABCD":
        ws2.column_dimensions[col].width = 18

    nota = ws2.max_row + 2
    ws2.cell(row=nota, column=1, value="Avanço físico ponderado em HH. Realizado = última medição datada de cada subetapa até o fim da semana.")
    if info["pct_sem_data"] > 0:
        ws2.cell(row=nota + 1, column=1,
                 value=f"Atenção: {info['pct_sem_data']:.1%} de avanço vem de medições SEM DATA e não aparece na curva.")

    if linhas:
        curva = LineChart()
        curva.title = "Curva S - Previsto x Realizado"
        curva.y_axis.title, curva.x_axis.title = "Avanço acumulado", "Fim da semana"
        curva.y_axis.number_format = "0%"
        curva.y_axis.scaling.min, curva.y_axis.scaling.max = 0, 1
        curva.add_data(Reference(ws2, min_col=2, max_col=3, min_row=1, max_row=1 + len(linhas)), titles_from_data=True)
        curva.set_categories(Reference(ws2, min_col=1, min_row=2, max_row=1 + len(linhas)))
        for serie in curva.series:
            serie.smooth = False  # linhas retas: não inventa valores entre as semanas
        curva.height, curva.width = 10, 24
        ws2.add_chart(curva, "F2")

    caminho = os.path.join(DIRETORIO_ATUAL, f"Histograma_e_Curva_S_{projeto_obj['nome'].replace(' ', '_')}.xlsx")
    wb.save(caminho)
    return caminho
