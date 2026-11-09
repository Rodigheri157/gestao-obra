import os
from modulos_geral import nome_subetapa, pasta_do_app
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from modulos_agenda import listar_subetapas_projeto
from modulos_calendario import gerar_dias_uteis, periodos_de_trabalho
from modulos_projetos import obter_valor_hh

# Exportação no formato MSPDI (XML do MS Project), seguindo o padrão Placore
# "Padrão Cronograma MS Project XML": a ORDEM dos elementos segue o schema
# mspdi_pj12.xsd — campos fora de ordem são descartados silenciosamente pelo Project.

DIRETORIO_ATUAL = pasta_do_app()

# Sigla do vínculo -> <Type> do PredecessorLink (0=TT, 1=TI, 2=IT, 3=II)
TIPO_LINK_MSP = {"TT": "0", "TI": "1", "IT": "2", "II": "3"}

# Campo personalizado Texto1 do Project, renomeado para "ID App": guarda o ID da
# subetapa para que a importação reconheça a tarefa mesmo se ela for movida no Project.
FIELD_ID_TEXTO1 = "188743731"
ALIAS_ID_APP = "ID App"


def _duracao_msp(horas):
    """Converte horas em 'PT{h}H{m}M0S' (formato de duração do MSPDI)."""
    minutos = round(horas * 60)
    return f"PT{minutos // 60}H{minutos % 60}M0S"


def _sub(pai, tag, texto=None):
    el = ET.SubElement(pai, tag)
    if texto is not None:
        el.text = str(texto)
    return el


def _memoria_calculo(sub):
    """Texto de <Notes> com a memória de cálculo da duração da subetapa."""
    qtd = sub.get("quantidade_fisica", 0.0)
    und = sub.get("unidade", "un")
    prod = sub.get("producao_equipe_dia", 0.0)
    n_eqp = sub.get("quantidade_equipes", 1)
    exec_ = sub.get("quantidade_executada", 0.0)
    pct = (min(1.0, exec_ / qtd) * 100) if qtd > 0 else 0.0
    eqp = ", ".join(f"{k} {v}" for k, v in sub.get("equipe_basica", {}).items()) or "não definida"
    texto = (
        f"Quantidade: {qtd} {und}. Produção: {prod} {und}/dia por equipe x {n_eqp} equipe(s). "
        f"Duração = arred. p/ cima({qtd} / ({prod} x {n_eqp})) = {sub.get('duracao_dias_planejada', 0)} dia(s) útil(eis). "
        f"Equipe básica por frente: {eqp}. Executado: {exec_} {und} ({pct:.1f}%). "
        f"Origem do índice: Catálogo de Etapas do app Gestão de Obra."
    )
    if sub.get("observacao"):
        texto += f" Obs.: {sub['observacao']}"
    return texto


def exportar_xml_projeto(projeto_obj, obras, cron, resumo):
    """Gera o XML (MSPDI) do projeto inteiro: Área > Obra > Disciplina > Etapa > Subetapa."""
    cal = resumo["calendario"]
    horas_dia = cal["horas_dia"]
    periodos = periodos_de_trabalho(horas_dia)
    hora_ini = periodos[0][0].strftime("%H:%M:%S")
    hora_fim = periodos[-1][1].strftime("%H:%M:%S")
    agora = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    project = ET.Element("Project", xmlns="http://schemas.microsoft.com/project")
    _sub(project, "SaveVersion", 14)  # obrigatório no schema (14 = MS Project 2010 ou superior)
    _sub(project, "Name", projeto_obj["nome"])
    _sub(project, "Title", f"Cronograma - {projeto_obj['nome']}")
    _sub(project, "Company", "Placore")
    _sub(project, "CreationDate", agora)
    _sub(project, "ScheduleFromStart", 1)
    _sub(project, "StartDate", f"{resumo['data_inicio'].isoformat()}T{hora_ini}")
    _sub(project, "FinishDate", f"{resumo['data_fim'].isoformat()}T{hora_fim}")
    _sub(project, "CurrencySymbol", "R$")
    _sub(project, "CurrencyCode", "BRL")  # obrigatório no schema
    _sub(project, "CalendarUID", 1)
    _sub(project, "DefaultStartTime", hora_ini)
    _sub(project, "DefaultFinishTime", hora_fim)
    _sub(project, "MinutesPerDay", round(horas_dia * 60))
    _sub(project, "MinutesPerWeek", round(horas_dia * 60 * len(cal["dias_uteis"])))
    _sub(project, "DaysPerMonth", round(len(cal["dias_uteis"]) * 52 / 12))
    _sub(project, "DefaultTaskType", 1)
    _sub(project, "DurationFormat", 7)
    # Data de status (última medição/data real): o Project reprograma o saldo a partir dela.
    # No schema, StatusDate vem antes de CurrentDate.
    if resumo.get("data_status"):
        _sub(project, "StatusDate", f"{resumo['data_status'].isoformat()}T{hora_fim}")
    _sub(project, "CurrentDate", agora)

    # ---------------- Campo personalizado "ID App" (vem antes de Calendars no schema) ----------------
    atributos = _sub(project, "ExtendedAttributes")
    atributo = _sub(atributos, "ExtendedAttribute")
    _sub(atributo, "FieldID", FIELD_ID_TEXTO1)
    _sub(atributo, "FieldName", "Text1")
    _sub(atributo, "Alias", ALIAS_ID_APP)

    # ---------------- Calendário ----------------
    calendarios = _sub(project, "Calendars")
    calendario = _sub(calendarios, "Calendar")
    _sub(calendario, "UID", 1)
    _sub(calendario, "Name", cal["nome"])
    _sub(calendario, "IsBaseCalendar", 1)
    _sub(calendario, "BaseCalendarUID", -1)
    weekdays = _sub(calendario, "WeekDays")
    for day_type in range(1, 8):  # 1 = Domingo ... 7 = Sábado
        dia_python = (day_type + 5) % 7  # converte para date.weekday() (0 = Segunda)
        wd = _sub(weekdays, "WeekDay")
        _sub(wd, "DayType", day_type)
        trabalha = dia_python in cal["dias_uteis"]
        _sub(wd, "DayWorking", 1 if trabalha else 0)
        if trabalha:
            wts = _sub(wd, "WorkingTimes")
            for ini, fim in periodos:
                wt = _sub(wts, "WorkingTime")
                _sub(wt, "FromTime", ini.strftime("%H:%M:%S"))
                _sub(wt, "ToTime", fim.strftime("%H:%M:%S"))
    for feriado in cal["feriados"]:  # feriados/paradas: DayType 0 + TimePeriod
        wd = _sub(weekdays, "WeekDay")
        _sub(wd, "DayType", 0)
        _sub(wd, "DayWorking", 0)
        tp = _sub(wd, "TimePeriod")
        _sub(tp, "FromDate", f"{feriado}T00:00:00")
        _sub(tp, "ToDate", f"{feriado}T23:59:00")

    # ---------------- Tarefas (WBS) ----------------
    tarefas_el = _sub(project, "Tasks")
    contador = {"uid": 0}

    def nova_tarefa(nome, wbs, nivel, resumo_flag):
        t = _sub(tarefas_el, "Task")
        _sub(t, "UID", contador["uid"])
        _sub(t, "ID", contador["uid"])
        _sub(t, "Name", nome)
        _sub(t, "Type", 1)
        _sub(t, "IsNull", 0)
        _sub(t, "WBS", wbs)
        _sub(t, "OutlineNumber", wbs)
        _sub(t, "OutlineLevel", nivel)
        if resumo_flag:
            _sub(t, "Summary", 1)
        contador["uid"] += 1
        return t

    raiz = nova_tarefa(projeto_obj["nome"].upper(), "0", 0, True)
    _sub(raiz, "Notes", f"Gerado pelo app Gestão de Obra em {datetime.now():%d/%m/%Y %H:%M}. "
                        f"Valor do HH: R$ {obter_valor_hh(projeto_obj):.2f}/HH (taxa padrão de todos os recursos; "
                        f"Custo = HH x valor, para ponderar o avanço por HH).")

    # Agrupa as obras do projeto por área, na ordem cadastrada no projeto
    obras_proj = [ob for ob in obras if ob.get("projeto_nome") == projeto_obj["nome"] and ob.get("disciplinas")]
    ordem_areas = list(projeto_obj.get("areas", {}))
    ordem_areas += [ob["area_nome"] for ob in obras_proj if ob["area_nome"] not in ordem_areas]

    uid_por_sub = {}
    folhas = []  # (elemento Task, subetapa) para preencher após conhecer todos os UIDs
    n_area = 0
    for area in ordem_areas:
        obras_area = [ob for ob in obras_proj if ob["area_nome"] == area]
        # Obras na ordem cadastrada na área (as não cadastradas vão para o fim)
        ordem_obras = projeto_obj.get("areas", {}).get(area, [])
        obras_area.sort(key=lambda ob: ordem_obras.index(ob["obra_nome"]) if ob["obra_nome"] in ordem_obras
                        else len(ordem_obras))
        if not obras_area:
            continue
        n_area += 1
        nova_tarefa(area, f"{n_area}", 1, True)
        for n_ob, ob in enumerate(obras_area, 1):
            wbs_ob = f"{n_area}.{n_ob}"
            nova_tarefa(ob["obra_nome"], wbs_ob, 2, True)
            for n_disc, (disc, etapas) in enumerate(ob["disciplinas"].items(), 1):
                wbs_disc = f"{wbs_ob}.{n_disc}"
                nova_tarefa(disc, wbs_disc, 3, True)
                for n_et, (etapa, subs) in enumerate(etapas.items(), 1):
                    wbs_et = f"{wbs_disc}.{n_et}"
                    nova_tarefa(etapa, wbs_et, 4, True)
                    for n_sub, sub in enumerate(subs, 1):
                        uid_por_sub[sub["id"]] = contador["uid"]
                        t = nova_tarefa(nome_subetapa(sub), f"{wbs_et}.{n_sub}", 5, False)
                        folhas.append((t, sub))

    # Dias úteis do projeto (para a data da restrição 'Não iniciar antes de')
    maior_restricao = max((s.get("dia_inicio_planejado", 1) for _, s in folhas), default=1)
    dias = gerar_dias_uteis(resumo["data_inicio"], max(resumo["duracao"], maior_restricao) + 1, cal)

    for t, sub in folhas:
        c = cron[sub["id"]]
        n_eqp = sub.get("quantidade_equipes", 1)
        pessoas = sum(sub.get("equipe_basica", {}).values()) * n_eqp
        horas = c["duracao"] * horas_dia
        pct = round(c["pct"] * 100)
        if c["situacao"] == "concluida":
            pct = 100
        elif c["situacao"] == "em_andamento":
            pct = min(pct, 99)  # em andamento nunca vai como 100% (o Project fecharia a tarefa)
        hora_termino = hora_ini if c["duracao"] == 0 else hora_fim

        _sub(t, "Start", f"{c['inicio'].isoformat()}T{hora_ini}")
        _sub(t, "Finish", f"{c['termino'].isoformat()}T{hora_termino}")
        _sub(t, "Duration", _duracao_msp(horas))
        _sub(t, "DurationFormat", 7)
        _sub(t, "Work", _duracao_msp(horas * pessoas))
        _sub(t, "Milestone", 1 if c["duracao"] == 0 else 0)
        _sub(t, "Summary", 0)
        _sub(t, "PercentComplete", pct)
        # Datas reais explícitas: sem elas o Project inventa o início real ao abrir o XML
        # (a tarefa fica presa nessa data e deixa de seguir as predecessoras).
        # No schema, ActualStart/ActualFinish vêm depois de PercentComplete e antes de ConstraintType.
        if c["situacao"] != "nao_iniciada":
            _sub(t, "ActualStart", f"{c['inicio'].isoformat()}T{hora_ini}")
            if c["situacao"] == "concluida":
                _sub(t, "ActualFinish", f"{c['termino'].isoformat()}T{hora_termino}")
        dia_restricao = sub.get("dia_inicio_planejado", 1)
        if dia_restricao > 1 and c["situacao"] == "nao_iniciada":
            _sub(t, "ConstraintType", 4)  # 4 = Não iniciar antes de
            _sub(t, "ConstraintDate", f"{dias[dia_restricao - 1].isoformat()}T{hora_ini}")
        notas = _memoria_calculo(sub)
        if c["fora_sequencia"]:
            notas += (f" ATENÇÃO: iniciada fora da sequência — início real anterior ao permitido pela(s) "
                      f"predecessora(s) {', '.join(f'#{p}' for p in c['fora_sequencia'])}.")
        _sub(t, "Notes", notas)
        for v in sub.get("predecessoras", []):
            if v["id"] not in uid_por_sub:
                continue
            link = _sub(t, "PredecessorLink")
            _sub(link, "PredecessorUID", uid_por_sub[v["id"]])
            _sub(link, "Type", TIPO_LINK_MSP.get(v.get("tipo", "TI"), "1"))
            # LinkLag é sempre em décimos de minuto
            _sub(link, "LinkLag", round(v.get("lag_dias", 0) * horas_dia * 60 * 10))
            _sub(link, "LagFormat", 7)
        # ExtendedAttribute vem depois de PredecessorLink no schema
        ext = _sub(t, "ExtendedAttribute")
        _sub(ext, "FieldID", FIELD_ID_TEXTO1)
        _sub(ext, "Value", sub["id"])

    # ---------------- Recursos (profissões) ----------------
    tarefas = listar_subetapas_projeto(obras_proj, projeto_obj["nome"])
    demanda_diaria = {}  # profissão -> {índice do dia útil: pessoas}
    for tid, info in tarefas.items():
        sub, c = info["sub"], cron[tid]
        for prof, qtd in sub.get("equipe_basica", {}).items():
            por_dia = demanda_diaria.setdefault(prof, {})
            for d in range(c["es"], c["ef"]):
                por_dia[d] = por_dia.get(d, 0) + qtd * sub.get("quantidade_equipes", 1)

    valor_hh = obter_valor_hh(projeto_obj)
    recursos_el = _sub(project, "Resources")
    uid_recurso = {}
    for n, prof in enumerate(sorted(demanda_diaria), 1):
        uid_recurso[prof] = n
        r = _sub(recursos_el, "Resource")
        _sub(r, "UID", n)
        _sub(r, "ID", n)
        _sub(r, "Name", prof)
        _sub(r, "Type", 1)
        # Disponibilidade = pico de demanda simultânea (evita falsa superalocação)
        _sub(r, "MaxUnits", max(demanda_diaria[prof].values(), default=1))
        # Mesmo valor por HH para todas as profissões: Custo = HH x valor, o que permite
        # ponderar o avanço do cronograma por HH (valor agregado / % físico) no Project.
        _sub(r, "StandardRate", valor_hh)
        _sub(r, "StandardRateFormat", 2)  # 2 = por hora

    # ---------------- Atribuições (histograma de mão de obra) ----------------
    atribuicoes = _sub(project, "Assignments")
    n_atrib = 0
    for t, sub in folhas:
        c = cron[sub["id"]]
        if c["duracao"] == 0:
            continue
        for prof, qtd in sub.get("equipe_basica", {}).items():
            unidades = qtd * sub.get("quantidade_equipes", 1)
            n_atrib += 1
            a = _sub(atribuicoes, "Assignment")
            _sub(a, "UID", n_atrib)
            _sub(a, "TaskUID", uid_por_sub[sub["id"]])
            _sub(a, "ResourceUID", uid_recurso[prof])
            _sub(a, "Units", unidades)
            _sub(a, "Work", _duracao_msp(unidades * c["duracao"] * horas_dia))

    arvore = ET.ElementTree(project)
    ET.indent(arvore, space="  ")
    nome_arq = f"Cronograma_{projeto_obj['nome'].replace(' ', '_')}.xml"
    caminho = os.path.join(DIRETORIO_ATUAL, nome_arq)
    arvore.write(caminho, encoding="utf-8", xml_declaration=True)
    return caminho
