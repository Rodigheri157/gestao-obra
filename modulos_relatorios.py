from datetime import date
from modulos_agenda import (
    CicloDeVinculos,
    calcular_cronograma,
    descrever_vinculo,
    listar_subetapas_projeto,
)
from modulos_calendario import converter_data, descrever_calendario
from modulos_geral import (
    nome_subetapa,
    ler_float,
    limpar_terminal,
    selecionar_item_lista,
)
from modulos_histograma import exportar_histograma_curva_s_excel, visualizar_histograma_curva_s
from modulos_importacao_msp import importar_xml_project
from modulos_msproject import exportar_xml_projeto
from modulos_obras import atualizar_quantidade_executada, carregar_obras, salvar_obras
from modulos_memorial import exportar_memorial_area, hh_subetapa, importar_memorial_area, obras_da_area
from modulos_projetos import carregar_projetos, descrever_valor_hh, obter_valor_hh

# ==============================================================================
# 1. LANÇAMENTO DE AVANÇO FÍSICO (ABA 2 DA OBRA)
# ==============================================================================

def lancar_nova_medicao(sub_ref):
    """Registra uma medição datada (quantidade acumulada). Retorna True se gravou."""
    qtd_p = sub_ref.get("quantidade_fisica", 0.0)
    und = sub_ref.get("unidade", "un")

    texto_data = input(f"\nData da medição (DD/MM/AAAA) [{date.today():%d/%m/%Y}]: ").strip()
    data_med = converter_data(texto_data) if texto_data else date.today()
    if not data_med:
        input("\n⚠️ Data inválida. Pressione Enter...")
        return False

    novo_real = ler_float(f"Quantidade Executada ACUMULADA até {data_med:%d/%m/%Y} ({und}): ", valor_padrao=-1)
    if novo_real < 0:
        input("\n⚠️ Quantidade não informada. Pressione Enter...")
        return False

    # Validação: executado acima do previsto exige confirmação
    if novo_real > qtd_p:
        print(f"\n⚠️ O valor informado ({novo_real} {und}) excede a Quantidade Prevista ({qtd_p} {und}).")
        confirma = input("Confirmar mesmo assim? O avanço será limitado a 100% nos relatórios (S/N): ").strip().upper()
        if confirma != "S":
            input("\nOperação cancelada. Pressione Enter...")
            return False

    # Validação: acumulado menor que o de uma medição anterior (possível erro de digitação)
    anteriores = [m for m in sub_ref["medicoes"] if m["data"] is None or m["data"] < data_med.isoformat()]
    if anteriores and novo_real < anteriores[-1]["acumulado"]:
        print(f"\n⚠️ O acumulado informado é MENOR que o da medição anterior ({anteriores[-1]['acumulado']} {und}).")
        if input("É uma correção intencional? (S/N): ").strip().upper() != "S":
            input("\nOperação cancelada. Pressione Enter...")
            return False

    # Já existe medição nesta data: substitui
    mesma_data = [m for m in sub_ref["medicoes"] if m["data"] == data_med.isoformat()]
    if mesma_data:
        if input(f"\n⚠️ Já existe medição em {data_med:%d/%m/%Y} ({mesma_data[0]['acumulado']} {und}). Substituir? (S/N): ").strip().upper() != "S":
            return False
        mesma_data[0]["acumulado"] = novo_real
    else:
        sub_ref["medicoes"].append({"data": data_med.isoformat(), "acumulado": novo_real})

    atualizar_quantidade_executada(sub_ref)
    return True


def gerenciar_medicoes_subetapa(sub_ref, obra_obj, todas_obras):
    """Exibe o histórico de medições da subetapa e permite lançar, datar ou excluir medições."""
    while True:
        qtd_p = sub_ref.get("quantidade_fisica", 0.0)
        und = sub_ref.get("unidade", "un")
        limpar_terminal()
        print(f"--- MEDIÇÃO DE CAMPO: #{sub_ref['id']} {nome_subetapa(sub_ref).upper()} ({obra_obj['obra_nome']}) ---")
        print(f"Quantidade Prevista Total: {qtd_p} {und}")
        print(f"Quantidade Executada Atual: {sub_ref.get('quantidade_executada', 0.0)} {und}\n")

        if qtd_p <= 0:
            print("❌ Esta subetapa não possui Quantidade Prevista cadastrada (0).")
            print("Cadastre o quantitativo físico na Gestão de Obras antes de lançar a medição.")
            input("\nPressione Enter para continuar...")
            return

        print("Histórico de medições (quantidade acumulada):")
        if not sub_ref["medicoes"]:
            print("  └── (Nenhuma medição lançada)")
        for i, m in enumerate(sub_ref["medicoes"], 1):
            data_txt = converter_data(m["data"]).strftime("%d/%m/%Y") if m["data"] else "SEM DATA  "
            pct = min(1.0, m["acumulado"] / qtd_p) * 100
            print(f"  {i}. {data_txt} | {m['acumulado']:>10.1f} {und} | {pct:>5.1f}%")

        sem_data = [m for m in sub_ref["medicoes"] if m["data"] is None]
        print("\n" + "-" * 50)
        print("1. Lançar Nova Medição")
        if sem_data:
            print("2. Informar Data de Medição 'SEM DATA' (para entrar na Curva S)")
        print("3. Excluir Medição")
        print("0. Voltar\n")
        op = input("Escolha uma opção: ").strip()

        alterou = False
        if op == "1":
            alterou = lancar_nova_medicao(sub_ref)
        elif op == "2" and sem_data:
            data_med = converter_data(input("\nData real da medição (DD/MM/AAAA): "))
            if data_med:
                sem_data[0]["data"] = data_med.isoformat()
                atualizar_quantidade_executada(sub_ref)
                alterou = True
            else:
                input("\n⚠️ Data inválida. Pressione Enter...")
        elif op == "3" and sub_ref["medicoes"]:
            n = input("\nNúmero da medição a excluir: ").strip()
            if n.isdigit() and 1 <= int(n) <= len(sub_ref["medicoes"]):
                if input("Confirmar exclusão? (S/N): ").strip().upper() == "S":
                    sub_ref["medicoes"].pop(int(n) - 1)
                    atualizar_quantidade_executada(sub_ref)
                    alterou = True
        elif op == "0":
            return

        if alterou:
            salvar_obras(todas_obras)
            pct = min(1.0, sub_ref["quantidade_executada"] / qtd_p) * 100
            input(f"\n✓ Histórico salvo. Executado atual: {sub_ref['quantidade_executada']} {und} ({pct:.1f}%). Pressione Enter...")


def lancar_avanco_subetapas(obra_obj, todas_obras):
    """Lista as subetapas da obra e abre o histórico de medições da escolhida (Lançamento da Aba 2)."""
    while True:
        limpar_terminal()
        print(f"=== LANÇAMENTO DE AVANÇO FÍSICO DA OBRA: {obra_obj['obra_nome'].upper()} ===")
        print(f"Projeto: {obra_obj['projeto_nome']} | Área: {obra_obj['area_nome']}\n")

        disciplinas = obra_obj.get("disciplinas", {})
        if not disciplinas:
            print("❌ Nenhuma subetapa cadastrada nesta obra.")
            input("\nPressione Enter para continuar...")
            return

        # Monta lista de subetapas para seleção rápida
        subetapas_flat = [
            (disc, etapa_nome, sub)
            for disc, etapas in disciplinas.items()
            for etapa_nome, subs in etapas.items()
            for sub in subs
        ]

        print(f"{'Nº':<4} | {'DISCIPLINA':<10} | {'ETAPA':<20} | {'SUBETAPA':<40} | {'PREVISTO':<10} | {'REAL':<10} | {'AVANÇO %':<8} | ÚLT. MEDIÇÃO")
        print("-" * 110)

        for i, (disc, etapa_nome, sub) in enumerate(subetapas_flat, 1):
            qtd_p = sub.get("quantidade_fisica", 0.0)
            qtd_r = sub.get("quantidade_executada", 0.0)
            und = sub.get("unidade", "un")
            pct = (qtd_r / qtd_p * 100) if qtd_p > 0 else 0.0
            ultima = sub["medicoes"][-1] if sub.get("medicoes") else None
            ult_txt = "-" if not ultima else (converter_data(ultima["data"]).strftime("%d/%m/%Y") if ultima["data"] else "sem data")
            print(
                f"{i:<4} | {disc:<10} | {etapa_nome[:18]:<20} | {nome_subetapa(sub)[:38]:<40} | {qtd_p:>6.1f} {und:<3} | {qtd_r:>6.1f} {und:<3} | {pct:>6.1f}%  | {ult_txt}"
            )

        print("\n  0. Voltar ao Menu de Relatórios\n")
        op = input("Digite o número da subetapa para ver o histórico / lançar medição: ").strip()

        if op == "0":
            break

        if op.isdigit() and 1 <= int(op) <= len(subetapas_flat):
            gerenciar_medicoes_subetapa(subetapas_flat[int(op) - 1][2], obra_obj, todas_obras)


# ==============================================================================
# 2. MEMORIAL DA ÁREA NO TERMINAL (ABA 1: ÁREA E ETAPAS / ABA 2: SUBETAPAS)
# ==============================================================================

def calcular_hh_subetapa(sub, horas_dia):
    """HH planejado da subetapa = duração (dias úteis) x horas/dia x pessoas (equipe x nº de equipes)."""
    return hh_subetapa(sub, horas_dia)


def datas_da_etapa(subetapas, cron):
    """Início, término e duração (dias úteis) de uma etapa a partir do cronograma das subetapas."""
    itens = [cron[s["id"]] for s in subetapas]
    inicio = min(c["inicio"] for c in itens)
    termino = max(c["termino"] for c in itens)
    duracao = max(c["ef"] for c in itens) - min(c["es"] for c in itens)
    return inicio, termino, duracao


def _pct_sub(sub):
    qtd_p = sub.get("quantidade_fisica", 0.0)
    return min(1.0, sub.get("quantidade_executada", 0.0) / qtd_p) if qtd_p > 0 else 0.0


def _data_txt(iso):
    d = converter_data(iso or "")
    return f"{d:%d/%m/%y}" if d else "-"


def visualizar_memorial_area(proj_sel, area_nome, obras, cron, resumo):
    """Exibe o memorial da área: Aba 1 (Obra > Etapas, ponderado em HH) e Aba 2 (Subetapas)."""
    horas_dia = resumo["calendario"]["horas_dia"]
    valor_hh = obter_valor_hh(proj_sel)
    obras_area = obras_da_area(proj_sel, obras, area_nome)
    limpar_terminal()
    print("=" * 110)
    print("MEMORIAL DE CÁLCULO E AVANÇO FÍSICO")
    print(f"PROJETO: {proj_sel['nome']} | ÁREA: {area_nome} | {descrever_valor_hh(proj_sel)}")
    print("=" * 110 + "\n")
    if not obras_area:
        input("❌ Nenhuma obra desta área possui subetapas cadastradas. Pressione Enter...")
        return

    print("ABA 1: ÁREA E ETAPAS (PONDERAÇÃO EM HH)")
    print(f"{'EAP':<7} | {'OBRA / DISCIPLINA > ETAPA':<38} | {'INÍCIO':<8} | {'TÉRMINO':<8} | {'DUR':>4} | "
          f"{'HH':>8} | {'VALOR R$':>12} | {'AVANÇO':>7}")
    print("-" * 110)
    hh_area = hh_exec_area = 0.0
    for n_ob, ob in enumerate(obras_area, 1):
        print(f"{n_ob:<7} | {ob['obra_nome'].upper()[:38]:<38}")
        for n_disc, (disc, etapas) in enumerate(ob["disciplinas"].items(), 1):
            for n_et, (etapa_nome, subs) in enumerate(etapas.items(), 1):
                hh = sum(calcular_hh_subetapa(s, horas_dia) for s in subs)
                hh_exec = sum(calcular_hh_subetapa(s, horas_dia) * _pct_sub(s) for s in subs)
                inicio, termino, dur = datas_da_etapa(subs, cron)
                hh_area += hh
                hh_exec_area += hh_exec
                pct = hh_exec / hh * 100 if hh else 0.0
                eap = f"{n_ob}.{n_disc}.{n_et}"
                rot = f"  {disc} > {etapa_nome}"
                print(f"{eap:<7} | {rot[:38]:<38} | {inicio:%d/%m/%y} | {termino:%d/%m/%y} | {dur:>4} | "
                      f"{hh:>8.0f} | {hh * valor_hh:>12,.2f} | {pct:>6.1f}%")
    print("-" * 110)
    pct_area = hh_exec_area / hh_area * 100 if hh_area else 0.0
    print(f"TOTAL DA ÁREA: {hh_area:,.0f} HH | R$ {hh_area * valor_hh:,.2f} | "
          f"AVANÇO FÍSICO PONDERADO EM HH: {pct_area:.2f}%\n")

    print("ABA 2: SUBETAPAS (APONTAMENTO)")
    print(f"{'DESCRIÇÃO':<50} | {'UND':<4} | {'QTD PREV':>10} | {'QTD EXEC':>10} | {'INÍCIO REAL':<11} | TÉRMINO REAL")
    print("-" * 110)
    for ob in obras_area:
        print(f"[{ob['obra_nome'].upper()}]")
        for disc, etapas in ob["disciplinas"].items():
            for etapa_nome, subs in etapas.items():
                print(f"  {disc} > {etapa_nome}")
                for sub in subs:
                    print(f"    {nome_subetapa(sub)[:46]:<46} | {sub.get('unidade', 'un'):<4} | "
                          f"{sub.get('quantidade_fisica', 0.0):>10.2f} | {sub.get('quantidade_executada', 0.0):>10.2f} | "
                          f"{_data_txt(sub.get('inicio_real')):<11} | {_data_txt(sub.get('termino_real'))}")
    print("=" * 110)
    input("\nPressione Enter para continuar...")


# ==============================================================================
# 3. MEMORIAL EM EXCEL POR ÁREA (EMISSÃO E IMPORTAÇÃO)
# ==============================================================================

def exportar_memorial_excel(proj_sel, area_nome, obras, cron, resumo):
    limpar_terminal()
    caminho = exportar_memorial_area(proj_sel, area_nome, obras, cron, resumo, obter_valor_hh(proj_sel))
    if caminho:
        print("✓ MEMORIAL DA ÁREA GERADO COM SUCESSO!")
        print(f"Arquivo: {caminho}")
        print("\n • Aba 1 (Área e Etapas): Obra > Disciplina > Etapa com HH, valor, peso e avanço ponderado em HH.")
        print(" • Aba 2 (Subetapas): preencha as células AMARELAS (data de corte, qtd executada acumulada,")
        print("   início e término reais). As demais células estão bloqueadas.")
        print(" • Depois de preenchido, use 'Importar Memorial Preenchido' para absorver os avanços.")
    input("\nPressione Enter para continuar...")


# ==============================================================================
# 4. CRONOGRAMA DO PROJETO (TELA E MS PROJECT)
# ==============================================================================

def visualizar_cronograma_projeto(projeto_obj, obras, cron, resumo):
    """Exibe o cronograma calculado do projeto, destacando o caminho crítico."""
    limpar_terminal()
    print("=" * 100)
    print(f"CRONOGRAMA DO PROJETO: {projeto_obj['nome'].upper()}")
    print(f"Início: {resumo['data_inicio']:%d/%m/%Y} | Término: {resumo['data_fim']:%d/%m/%Y} | "
          f"Duração: {resumo['duracao']} dias úteis")
    print(descrever_calendario(resumo["calendario"]))
    if resumo["aviso"]:
        print(resumo["aviso"])
    if resumo.get("data_status"):
        print(f"Data de status (última medição/data real): {resumo['data_status']:%d/%m/%Y} — "
              f"saldos e atividades não iniciadas reprogramados a partir do dia útil seguinte")
    print("=" * 100)
    print(f"{'ID':<4} | {'OBRA':<16} | {'ETAPA':<18} | {'SUBETAPA':<40} | {'INÍCIO':<8} | {'TÉRMINO':<8} | {'DUR':<4} | {'FOLGA':<5} | {'AV.':>4} | PRED.")
    print("-" * 100)

    tarefas = listar_subetapas_projeto(obras, projeto_obj["nome"])
    simbolo = {"nao_iniciada": " ", "em_andamento": "►", "concluida": "✓"}
    for tid, t in sorted(tarefas.items(), key=lambda item: (cron[item[0]]["es"], item[0])):
        c = cron[tid]
        marca = "*" if c["critica"] else ("!" if c["fora_sequencia"] else " ")
        preds = ", ".join(descrever_vinculo(v) for v in t["sub"].get("predecessoras", [])) or "-"
        print(
            f"{marca}{tid:<3} | {t['obra']['obra_nome'][:16]:<16} | {t['etapa'][:18]:<18} | {nome_subetapa(t['sub'])[:40]:<40} | "
            f"{c['inicio']:%d/%m/%y} | {c['termino']:%d/%m/%y} | {c['duracao']:<4} | {c['folga']:<5} | "
            f"{simbolo[c['situacao']]}{c['pct'] * 100:>3.0f}% | {preds}"
        )

    print("-" * 100)
    print("* = caminho crítico (folga zero) | ! = iniciada fora da sequência | ► em andamento | ✓ concluída")
    print("Datas de atividades iniciadas/concluídas = datas reais do memorial; saldo reprogramado após a data de status.")

    fora = [(tid, cron[tid]) for tid in tarefas if cron[tid]["fora_sequencia"]]
    if fora:
        print("\n--- ATIVIDADES INICIADAS FORA DA SEQUÊNCIA (início real antes do permitido pelos vínculos) ---")
        for tid, c in sorted(fora, key=lambda x: x[0]):
            nomes = ", ".join(f"#{p} {nome_subetapa(tarefas[p]['sub'])[:40]}" for p in c["fora_sequencia"])
            print(f"  ! #{tid} {nome_subetapa(tarefas[tid]['sub'])[:40]} (início real {c['inicio']:%d/%m/%y}) "
                  f"antes de: {nomes}")
        print("  → Avalie se o vínculo ainda representa a lógica da obra (ajuste/remova) ou se foi uma antecipação pontual.")
    input("\nPressione Enter para continuar...")


# ==============================================================================
# MENU DE RELATÓRIOS E ANÁLISES
# ==============================================================================

def selecionar_obra_area(proj_sel, area_nome, obras):
    """Escolhe uma obra (com subetapas) da área. Retorna o objeto da obra ou None."""
    obras_area = obras_da_area(proj_sel, obras, area_nome)
    nome, idx = selecionar_item_lista([ob["obra_nome"] for ob in obras_area], titulo=f"Obras em '{area_nome}'")
    return obras_area[idx] if nome else None


def menu_area_relatorios(proj_sel, obras, cron, resumo):
    """Seleciona a Área e oferece medição, memorial (tela/Excel) e importação do memorial preenchido."""
    limpar_terminal()
    areas_dict = proj_sel.get("areas", {})
    if not areas_dict:
        print(f"\n❌ O projeto '{proj_sel['nome']}' não possui áreas.")
        input("\nPressione Enter para continuar...")
        return

    area_sel, _ = selecionar_item_lista(list(areas_dict.keys()), titulo="Selecione a Área")
    if not area_sel:
        return
    if not obras_da_area(proj_sel, obras, area_sel):
        print(f"\n❌ Nenhuma obra da área '{area_sel}' possui subetapas e quantitativos cadastrados.")
        input("\nPressione Enter para continuar...")
        return

    while True:
        limpar_terminal()
        print(f"=== MEMORIAL E MEDIÇÃO DA ÁREA: {area_sel.upper()} ===")
        print(f"Projeto: {proj_sel['nome']} | {descrever_valor_hh(proj_sel)}\n")
        print("1. Lançar Avanço Físico Executado de uma Obra (Medição de Campo)")
        print("2. Visualizar Memorial da Área (Área e Etapas / Subetapas)")
        print("3. Emitir Memorial da Área em Excel (.xlsx protegido, para apontamento)")
        print("4. Importar Memorial Preenchido (absorver avanços reportados)")
        print("0. Voltar\n")

        op = input("Escolha uma opção: ").strip()

        if op == "1":
            limpar_terminal()
            obra_obj = selecionar_obra_area(proj_sel, area_sel, obras)
            if obra_obj:
                lancar_avanco_subetapas(obra_obj, obras)
        elif op == "2":
            visualizar_memorial_area(proj_sel, area_sel, obras, cron, resumo)
        elif op == "3":
            exportar_memorial_excel(proj_sel, area_sel, obras, cron, resumo)
        elif op == "4":
            importar_memorial_area(proj_sel, area_sel, obras)
        elif op == "0":
            break


def menu_relatorios():
    """Navegação para selecionar o projeto e emitir cronograma, medições e relatórios."""
    while True:
        limpar_terminal()
        projetos = carregar_projetos()

        if not projetos:
            print("❌ Nenhum projeto cadastrado no sistema.")
            input("\nPressione Enter para continuar...")
            break

        print("=== MEDIÇÃO, MEMORIAIS E CRONOGRAMAS ===\n")
        proj_sel, _ = selecionar_item_lista(projetos, titulo="Selecione o Projeto", chave_nome="nome")
        if not proj_sel:
            break

        while True:
            obras = carregar_obras()
            try:
                cron, resumo = calcular_cronograma(obras, proj_sel)
            except (CicloDeVinculos, ValueError) as e:
                print(f"\n❌ Não foi possível calcular o cronograma: {e}")
                input("\nPressione Enter para continuar...")
                break

            limpar_terminal()
            print(f"=== PROJETO: {proj_sel['nome'].upper()} ===")
            print(f"Início: {resumo['data_inicio']:%d/%m/%Y} | Término previsto: {resumo['data_fim']:%d/%m/%Y} | "
                  f"{resumo['duracao']} dias úteis")
            if resumo["aviso"]:
                print(resumo["aviso"])
            print("\n1. Visualizar Cronograma do Projeto (Caminho Crítico)")
            print("2. Exportar Cronograma para o MS Project (.xml)")
            print("3. Medição e Memorial por Área (Excel com importação dos avanços)")
            print("4. Histograma de Mão de Obra e Curva S (Tela)")
            print("5. Exportar Histograma e Curva S para o Excel (.xlsx com Gráficos)")
            print("6. Importar Predecessoras e Datas do MS Project (.xml)")
            print("0. Selecionar Outro Projeto\n")

            op = input("Escolha uma opção: ").strip()

            if op == "1":
                visualizar_cronograma_projeto(proj_sel, obras, cron, resumo)
            elif op == "2":
                caminho = exportar_xml_projeto(proj_sel, obras, cron, resumo)
                print(f"\n✓ Cronograma exportado para o MS Project: {caminho}")
                input("\nPressione Enter para continuar...")
            elif op == "3":
                menu_area_relatorios(proj_sel, obras, cron, resumo)
            elif op == "4":
                visualizar_histograma_curva_s(proj_sel, obras, cron, resumo)
            elif op == "5":
                caminho = exportar_histograma_curva_s_excel(proj_sel, obras, cron, resumo)
                if caminho:
                    print(f"\n✓ Histograma e Curva S exportados: {caminho}")
                input("\nPressione Enter para continuar...")
            elif op == "6":
                importar_xml_project(proj_sel, obras)  # o cronograma é recalculado no início do laço
            elif op == "0":
                break
