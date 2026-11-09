import math
from datetime import date, timedelta
from modulos_calendario import converter_data, eh_dia_util, gerar_dias_uteis, obter_calendario
from modulos_geral import nome_subetapa

# Tipos de vínculo (convenção brasileira do MS Project)
TIPOS_VINCULO = {
    "TI": "Término-Início",
    "II": "Início-Início",
    "TT": "Término-Término",
    "IT": "Início-Término",
}


class CicloDeVinculos(Exception):
    """Os vínculos de predecessão formam um ciclo (A depende de B que depende de A)."""


# ==============================================================================
# LEVANTAMENTO DAS ATIVIDADES DO PROJETO
# ==============================================================================

def listar_subetapas_projeto(obras, projeto_nome):
    """Retorna {id: {obra, disciplina, etapa, sub}} de todas as subetapas do projeto."""
    tarefas = {}
    for ob in obras:
        if ob.get("projeto_nome") != projeto_nome:
            continue
        for disc, etapas in ob.get("disciplinas", {}).items():
            for etapa_nome, subs in etapas.items():
                for sub in subs:
                    if "id" in sub:
                        tarefas[sub["id"]] = {"obra": ob, "disciplina": disc, "etapa": etapa_nome, "sub": sub}
    return tarefas


def descrever_vinculo(vinc):
    """Texto curto de um vínculo (ex.: '#3 TI+2d')."""
    lag = vinc.get("lag_dias", 0)
    txt_lag = f"{lag:+d}d" if lag else ""
    return f"#{vinc['id']} {vinc.get('tipo', 'TI')}{txt_lag}"


# ==============================================================================
# CÁLCULO DO CRONOGRAMA (MÉTODO DO CAMINHO CRÍTICO)
# ==============================================================================

def calcular_cronograma(obras, projeto_obj):
    """
    Calcula datas, folgas e caminho crítico de todas as subetapas do projeto.

    As contas são feitas em índices de dias úteis (0 = 1º dia útil do projeto) e
    convertidas para datas pelo calendário do projeto. O 'dia_inicio_planejado'
    da subetapa funciona como restrição 'Não iniciar antes de'.

    Avanço real (importado do memorial): atividade iniciada fica presa ao início real,
    mesmo que fora da sequência dos vínculos (registrado em 'fora_sequencia'); o saldo
    não executado e as atividades não iniciadas são reprogramados após a data de status.
    """
    if not projeto_obj:
        raise ValueError("Projeto não encontrado no cadastro de projetos.")
    tarefas = listar_subetapas_projeto(obras, projeto_obj["nome"])
    cal = obter_calendario(projeto_obj)

    aviso = ""
    data_inicio = converter_data(projeto_obj.get("data_inicio", ""))
    if not data_inicio:
        data_inicio = date.today()
        aviso = "⚠️ Data de início do projeto não definida/inválida: usando a data de hoje."

    # Vínculos válidos (ignora predecessoras que não existem mais)
    preds = {tid: [v for v in t["sub"].get("predecessoras", []) if v["id"] in tarefas and v["id"] != tid]
             for tid, t in tarefas.items()}
    sucessoras = {tid: [] for tid in tarefas}
    for tid, lista in preds.items():
        for v in lista:
            sucessoras[v["id"]].append((tid, v))

    # Ordenação topológica (detecta ciclos)
    pendentes = {tid: len(lista) for tid, lista in preds.items()}
    ordem = [tid for tid in tarefas if pendentes[tid] == 0]
    for tid in ordem:
        for suc_id, _ in sucessoras[tid]:
            pendentes[suc_id] -= 1
            if pendentes[suc_id] == 0:
                ordem.append(suc_id)

    if len(ordem) < len(tarefas):
        em_ciclo = [f"#{t} {nome_subetapa(tarefas[t]['sub'])}" for t in tarefas if pendentes[t] > 0]
        raise CicloDeVinculos("vínculos circulares envolvendo " + ", ".join(em_ciclo))

    dur = {tid: max(0, int(t["sub"].get("duracao_dias_planejada", 1))) for tid, t in tarefas.items()}

    # ---- Avanço real (memorial): datas reais e data de status ----
    # Data de status = data mais recente entre as medições e as datas reais apontadas.
    reais = {}
    datas_status = []
    for tid, t in tarefas.items():
        sub = t["sub"]
        ini_r = converter_data(sub.get("inicio_real") or "")
        fim_r = converter_data(sub.get("termino_real") or "")
        reais[tid] = (ini_r, fim_r, _pct_executado(sub))
        datas_status += [d for d in (ini_r, fim_r) if d]
        datas_status += [d for d in (converter_data(m.get("data") or "") for m in sub.get("medicoes", [])) if d]
    data_status = max(datas_status, default=None)
    if any(d < data_inicio for d in datas_status):
        aviso = (aviso + "\n" if aviso else "") + ("⚠️ Há datas reais/medições anteriores ao início do projeto: "
                                                   "no cálculo foram tratadas como o 1º dia útil.")

    def idx_inicio(d):
        """Data -> índice do dia útil em que a atividade começa (dia não útil vai para o próximo útil)."""
        return max(0, _contar_dias_uteis(data_inicio, d, cal))

    def idx_fim(d):
        """Data -> índice do último dia útil até a data (inclusive)."""
        return max(0, _contar_dias_uteis(data_inicio, d + timedelta(days=1), cal) - 1)

    st = idx_fim(data_status) if data_status else None  # índice do dia de status

    # Ida: datas mais cedo (ES = início, EF = término exclusivo)
    # - Não iniciada: segue vínculos e restrição, e não pode começar antes do dia seguinte ao status.
    # - Iniciada: o início é o REAL (mesmo fora da sequência lógica: o real prevalece sobre o planejado);
    #   o saldo (duração x % não executado) é reprogramado a partir do dia seguinte ao status.
    # - Concluída: início e término reais (sem término real, assume a data de status ou o término previsto).
    es, ef, situacao, fora_seq = {}, {}, {}, {}
    for tid in ordem:
        inicio = max(0, int(tarefas[tid]["sub"].get("dia_inicio_planejado", 1)) - 1)
        violados = []
        for v in preds[tid]:
            p, lag = v["id"], v.get("lag_dias", 0)
            tipo = v.get("tipo", "TI")
            if tipo == "TI":
                limite = ef[p] + lag
            elif tipo == "II":
                limite = es[p] + lag
            elif tipo == "TT":
                limite = ef[p] + lag - dur[tid]
            elif tipo == "IT":
                limite = es[p] + lag - dur[tid]
            else:
                continue
            violados.append((v, limite))
            inicio = max(inicio, limite)

        ini_r, fim_r, pct = reais[tid]
        if ini_r is None and fim_r is None and pct <= 0:
            situacao[tid] = "nao_iniciada"
            if st is not None:
                inicio = max(inicio, st + 1)
            es[tid] = inicio
            ef[tid] = inicio + dur[tid]
            continue

        # Iniciada ou concluída: o real prevalece
        es_real = idx_inicio(ini_r) if ini_r else (min(inicio, st) if st is not None else inicio)
        if fim_r:
            fim_real = max(es_real + (1 if dur[tid] else 0), idx_fim(fim_r) + 1)
            situacao[tid] = "concluida"
        elif pct >= 1:
            fim_real = es_real + dur[tid]
            if st is not None:
                fim_real = max(es_real + (1 if dur[tid] else 0), min(fim_real, st + 1))
            situacao[tid] = "concluida"
        else:
            restante = math.ceil(dur[tid] * (1 - pct) - 1e-9)
            inicio_saldo = max(es_real, st + 1) if st is not None else es_real + (dur[tid] - restante)
            fim_real = inicio_saldo + restante
            situacao[tid] = "em_andamento"
        es[tid], ef[tid] = es_real, fim_real
        # Registra os vínculos que o início real desrespeitou (execução fora de sequência)
        fora_seq[tid] = [v["id"] for v, limite in violados if es_real < limite]

    dur_efetiva = {tid: ef[tid] - es[tid] for tid in tarefas}
    fim_projeto = max(ef.values(), default=0)

    # Volta: datas mais tarde e folga total
    lf = {}
    for tid in reversed(ordem):
        limite = fim_projeto
        for suc_id, v in sucessoras[tid]:
            lag, tipo = v.get("lag_dias", 0), v.get("tipo", "TI")
            if situacao[suc_id] == "concluida":
                continue  # sucessora já concluída não impõe limite
            if situacao[suc_id] == "em_andamento" and tipo in ("TI", "II"):
                continue  # sucessora já iniciada: o início dela é real e não depende mais desta
            ls_suc = lf[suc_id] - dur_efetiva[suc_id]
            if tipo == "TI":
                limite = min(limite, ls_suc - lag)
            elif tipo == "II":
                limite = min(limite, ls_suc - lag + dur_efetiva[tid])
            elif tipo == "TT":
                limite = min(limite, lf[suc_id] - lag)
            elif tipo == "IT":
                limite = min(limite, lf[suc_id] - lag + dur_efetiva[tid])
        lf[tid] = limite

    # Conversão de índices de dia útil em datas reais
    dias = gerar_dias_uteis(data_inicio, fim_projeto + 1, cal)

    resultado = {}
    for tid in tarefas:
        ini_r, fim_r, pct = reais[tid]
        folga = 0 if situacao[tid] == "concluida" else lf[tid] - ef[tid]
        resultado[tid] = {
            "es": es[tid],
            "ef": ef[tid],
            "duracao": dur_efetiva[tid],
            "duracao_planejada": dur[tid],
            "folga": folga,
            "critica": situacao[tid] != "concluida" and folga <= 0,
            "inicio": ini_r or dias[es[tid]],
            "termino": fim_r or dias[max(es[tid], ef[tid] - 1)],
            "situacao": situacao[tid],          # nao_iniciada | em_andamento | concluida
            "pct": pct,
            "inicio_real": ini_r,
            "termino_real": fim_r,
            "fora_sequencia": fora_seq.get(tid, []),  # IDs das predecessoras desrespeitadas pelo início real
        }

    resumo = {
        "data_inicio": dias[0],
        "data_fim": dias[max(0, fim_projeto - 1)],
        "duracao": fim_projeto,
        "calendario": cal,
        "aviso": aviso,
        "data_status": data_status,
    }
    return resultado, resumo


def _pct_executado(sub):
    """Fração executada da subetapa (0 a 1)."""
    qtd = sub.get("quantidade_fisica", 0.0)
    return min(1.0, sub.get("quantidade_executada", 0.0) / qtd) if qtd > 0 else 0.0


def _contar_dias_uteis(inicio, fim, cal):
    """Quantidade de dias úteis no intervalo [inicio, fim). Negativa se fim < inicio."""
    if fim < inicio:
        return -_contar_dias_uteis(fim, inicio, cal)
    n, cursor = 0, inicio
    while cursor < fim:
        if eh_dia_util(cursor, cal):
            n += 1
        cursor += timedelta(days=1)
    return n
