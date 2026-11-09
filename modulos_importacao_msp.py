import copy
import os
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import date, datetime
from modulos_agenda import CicloDeVinculos, calcular_cronograma, descrever_vinculo, listar_subetapas_projeto
from modulos_calendario import converter_data, gerar_dias_uteis, obter_calendario
from modulos_geral import nome_subetapa, pasta_do_app, limpar_terminal, selecionar_item_lista
from modulos_msproject import ALIAS_ID_APP, FIELD_ID_TEXTO1
from modulos_obras import ARQUIVO_OBRAS, salvar_obras

# Importação de predecessoras e datas a partir de um XML (MSPDI) salvo pelo MS Project.
#
# Regras:
# - Tarefa do Project -> subetapa do app: pelo campo "ID App" (Texto1) gravado na exportação;
#   se vazio, pelo caminho de nomes Área > Obra > Disciplina > Etapa > Subetapa.
# - O Project passa a ser a fonte das predecessoras: as de cada subetapa reconhecida são SUBSTITUÍDAS.
# - Vínculo com tarefa-resumo é distribuído para todas as subetapas abaixo dela.
# - Datas: a restrição/data de início do Project vira o 'dia_inicio_planejado' da subetapa.
#   A duração NÃO é importada (no app ela vem do memorial: quantidade / produção) — só é comparada.

NS = {"p": "http://schemas.microsoft.com/project"}
DIRETORIO_ATUAL = pasta_do_app()

TIPO_LINK_APP = {"0": "TT", "1": "TI", "2": "IT", "3": "II"}
# LagFormat do MSPDI (o "estimado" é o mesmo código + 32)
FORMATOS_DECORRIDOS = {4, 6, 8, 10, 12}
FORMATOS_PERCENTUAIS = {19, 20}
NOMES_RESTRICAO = {
    0: "O Mais Breve Possível", 1: "O Mais Tarde Possível", 2: "Deve Iniciar Em", 3: "Deve Terminar Em",
    4: "Não Iniciar Antes De", 5: "Não Iniciar Depois De", 6: "Não Terminar Antes De", 7: "Não Terminar Depois De",
}


# ==============================================================================
# LEITURA DO XML
# ==============================================================================

def _txt(el, tag, padrao=None):
    filho = el.find(f"p:{tag}", NS)
    return filho.text if filho is not None and filho.text is not None else padrao


def _data(texto):
    """'2026-01-05T08:00:00' -> date."""
    return datetime.fromisoformat(texto).date() if texto else None


def _horas_duracao(texto):
    """'PT40H0M0S' -> 40.0 horas."""
    m = re.match(r"PT(\d+(?:\.\d+)?)H(\d+(?:\.\d+)?)M(\d+(?:\.\d+)?)S", texto or "")
    return float(m.group(1)) + float(m.group(2)) / 60 + float(m.group(3)) / 3600 if m else 0.0


def ler_tarefas_xml(caminho):
    """Lê o XML e retorna (nome do projeto, lista de tarefas com hierarquia, vínculos e datas)."""
    raiz = ET.parse(caminho).getroot()
    if not raiz.tag.endswith("Project"):
        raise ValueError("o arquivo não é um XML do MS Project (MSPDI).")

    # Descobre o FieldID do campo "ID App" (normalmente Texto1, mas aceita outro campo com esse alias)
    field_ids = {FIELD_ID_TEXTO1}
    for ea in raiz.findall("p:ExtendedAttributes/p:ExtendedAttribute", NS):
        if (_txt(ea, "Alias") or "").strip().lower() == ALIAS_ID_APP.lower():
            field_ids.add(_txt(ea, "FieldID"))

    tarefas = []
    pilha = []  # caminho de nomes por nível de estrutura
    for t in raiz.findall("p:Tasks/p:Task", NS):
        if _txt(t, "IsNull") == "1" or _txt(t, "Name") is None:
            continue
        nivel = int(_txt(t, "OutlineLevel", "0"))
        nome = _txt(t, "Name").strip()
        pilha = pilha[:max(0, nivel - 1)] + [nome] if nivel > 0 else []
        id_app = None
        for ea in t.findall("p:ExtendedAttribute", NS):
            if _txt(ea, "FieldID") in field_ids and (_txt(ea, "Value") or "").strip().isdigit():
                id_app = int(_txt(ea, "Value").strip())
        tarefas.append({
            "uid": _txt(t, "UID"),
            "nome": nome,
            "wbs": _txt(t, "OutlineNumber", ""),
            "nivel": nivel,
            "caminho": tuple(pilha),
            "resumo": _txt(t, "Summary") == "1",
            "manual": _txt(t, "Manual") == "1",
            "inicio": _data(_txt(t, "Start")),
            "termino": _data(_txt(t, "Finish")),
            "horas": _horas_duracao(_txt(t, "Duration")),
            "restricao": int(_txt(t, "ConstraintType", "0")),
            "data_restricao": _data(_txt(t, "ConstraintDate")),
            "id_app": id_app,
            "vinculos": [
                {
                    "uid": _txt(v, "PredecessorUID"),
                    "tipo": _txt(v, "Type", "1"),
                    "lag": float(_txt(v, "LinkLag", "0")),
                    "formato": int(_txt(v, "LagFormat", "7")),
                }
                for v in t.findall("p:PredecessorLink", NS)
            ],
        })
    return _txt(raiz, "Name", ""), tarefas


# ==============================================================================
# ANÁLISE (não altera nada: devolve uma cópia das obras com as mudanças + relatório)
# ==============================================================================

def _converter_lag(v, horas_dia, cal, avisos, rotulo):
    """LinkLag (décimos de minuto) -> dias úteis inteiros."""
    fmt = v["formato"] - 32 if v["formato"] >= 35 else v["formato"]
    if fmt in FORMATOS_PERCENTUAIS:
        avisos.append(f"{rotulo}: defasagem em % não é suportada pelo app — importada como 0d. Ajuste manualmente.")
        return 0
    minutos = v["lag"] / 10
    if fmt in FORMATOS_DECORRIDOS:
        dias = minutos / 60 / 24 * len(cal["dias_uteis"]) / 7
        avisos.append(f"{rotulo}: defasagem em dias corridos convertida por aproximação para {round(dias)}d úteis.")
    else:
        dias = minutos / 60 / horas_dia
    if abs(dias - round(dias)) > 0.01:
        avisos.append(f"{rotulo}: defasagem de {dias:.2f}d arredondada para {round(dias)}d (o app usa dias inteiros).")
    return int(round(dias))


def analisar_importacao(caminho_xml, obras, projeto_obj):
    """Monta o plano de importação. Retorna dict com obras_novas, mudanças, avisos e comparação de datas."""
    nome_xml, tarefas_xml = ler_tarefas_xml(caminho_xml)
    cal = obter_calendario(projeto_obj)
    horas_dia = cal["horas_dia"]
    avisos = []
    if nome_xml and nome_xml != projeto_obj["nome"]:
        avisos.append(f"O XML se chama '{nome_xml}', mas o projeto selecionado é '{projeto_obj['nome']}'.")

    obras_novas = copy.deepcopy(obras)
    subs_app = listar_subetapas_projeto(obras_novas, projeto_obj["nome"])
    por_caminho = {}
    for sid, t in subs_app.items():
        chave = (t["obra"]["area_nome"], t["obra"]["obra_nome"], t["disciplina"], t["etapa"], nome_subetapa(t["sub"]))
        por_caminho.setdefault(chave, []).append(sid)

    # ---- 1. Correspondência tarefa do Project -> subetapa do app ----
    uid_para_sub = {}
    por_uid = {t["uid"]: t for t in tarefas_xml}
    for t in tarefas_xml:
        if t["resumo"] or t["nivel"] == 0:
            continue
        sid = t["id_app"] if t["id_app"] in subs_app else None
        if sid is None:
            candidatos = por_caminho.get(t["caminho"][-5:], []) if len(t["caminho"]) >= 5 else []
            if len(candidatos) == 1:
                sid = candidatos[0]
            elif len(candidatos) > 1:
                avisos.append(f"Tarefa '{t['wbs']} {t['nome']}': nome repetido na etapa, sem 'ID App' — ignorada.")
                continue
        if sid is None:
            avisos.append(f"Tarefa '{t['wbs']} {t['nome']}' existe só no Project (não reconhecida) — ignorada.")
            continue
        if sid in uid_para_sub.values():
            avisos.append(f"Subetapa #{sid} aparece mais de uma vez no Project — usada só a 1ª ocorrência.")
            continue
        uid_para_sub[t["uid"]] = sid

    # Subetapas sob cada tarefa (folha = ela mesma; resumo = todas as folhas abaixo dela)
    folhas_de = {}
    for i, t in enumerate(tarefas_xml):
        if t["uid"] in uid_para_sub:
            folhas_de[t["uid"]] = [uid_para_sub[t["uid"]]]
        elif t["resumo"] or t["nivel"] == 0:
            lista = []
            for d in tarefas_xml[i + 1:]:
                if d["nivel"] <= t["nivel"]:
                    break
                if d["uid"] in uid_para_sub:
                    lista.append(uid_para_sub[d["uid"]])
            folhas_de[t["uid"]] = lista

    # ---- 2. Predecessoras (com distribuição de vínculos de tarefas-resumo) ----
    novas_preds = {sid: [] for sid in uid_para_sub.values()}
    for t in tarefas_xml:
        for v in t["vinculos"]:
            pred = por_uid.get(v["uid"])
            rotulo = f"Vínculo '{pred['nome'] if pred else v['uid']}' -> '{t['nome']}'"
            if pred is None or v["uid"] not in folhas_de or t["uid"] not in folhas_de:
                avisos.append(f"{rotulo}: envolve tarefa não reconhecida no app — ignorado "
                              f"(se ela ficava entre duas subetapas, essa sequência se perde).")
                continue
            tipo = TIPO_LINK_APP.get(v["tipo"], "TI")
            lag = _converter_lag(v, horas_dia, cal, avisos, rotulo)
            if pred["resumo"] and tipo in ("II", "IT"):
                avisos.append(f"{rotulo}: vínculo {tipo} a partir de resumo distribuído para TODAS as subetapas — "
                              f"no app fica mais restritivo (considera o início mais tarde entre elas).")
            if t["resumo"] and tipo in ("TT", "IT"):
                avisos.append(f"{rotulo}: vínculo {tipo} chegando em resumo distribuído para todas as subetapas — confira.")
            if pred["resumo"] or t["resumo"]:
                avisos.append(f"{rotulo}: vínculo de tarefa-resumo distribuído "
                              f"({len(folhas_de[v['uid']])} x {len(folhas_de[t['uid']])} subetapas).")
            for s in folhas_de[t["uid"]]:
                for p in folhas_de[v["uid"]]:
                    if s == p:
                        continue
                    existente = next((x for x in novas_preds[s] if x["id"] == p), None)
                    if existente is None:
                        novas_preds[s].append({"id": p, "tipo": tipo, "lag_dias": lag})
                    elif (existente["tipo"], existente["lag_dias"]) != (tipo, lag):
                        avisos.append(f"Subetapa #{s}: vínculos diferentes com #{p} (resumo + tarefa) — mantido "
                                      f"{descrever_vinculo(existente)}, descartado {tipo}{lag:+d}d.")

    # ---- 3. Datas de início (restrições do Project -> dia_inicio_planejado) ----
    data_inicio = converter_data(projeto_obj.get("data_inicio", "")) or date.today()
    datas_xml = [d for t in tarefas_xml for d in (t["inicio"], t["termino"], t["data_restricao"]) if d]
    ultimo = max(datas_xml, default=data_inicio)
    dias = gerar_dias_uteis(data_inicio, max(1, (ultimo - data_inicio).days + 2), cal)

    def dia_util(d):
        """Data -> nº do dia útil do projeto (1 = 1º dia). Dia não útil avança para o próximo útil."""
        if d < data_inicio:
            return 1
        return next((i + 1 for i, x in enumerate(dias) if x >= d), len(dias))

    sub_por_id = {sid: t["sub"] for sid, t in subs_app.items()}
    inicio_resumo = {}  # sid -> dia mínimo herdado de restrição em tarefa-resumo
    for t in tarefas_xml:
        if (t["resumo"] or t["nivel"] == 0) and t["restricao"] in (2, 4) and t["data_restricao"]:
            for s in folhas_de.get(t["uid"], []):
                inicio_resumo[s] = max(inicio_resumo.get(s, 1), dia_util(t["data_restricao"]))
            avisos.append(f"Resumo '{t['nome']}': restrição '{NOMES_RESTRICAO[t['restricao']]}' "
                          f"{t['data_restricao']:%d/%m/%Y} aplicada às subetapas abaixo dele.")

    novos_dias = {}
    for t in tarefas_xml:
        sid = uid_para_sub.get(t["uid"])
        if sid is None:
            continue
        sub = sub_por_id[sid]
        dur = int(sub.get("duracao_dias_planejada", 1))
        dur_xml = t["horas"] / horas_dia
        if abs(dur_xml - dur) > 0.01:
            avisos.append(f"#{sid} {nome_subetapa(sub)}: duração no Project = {dur_xml:g}d, no app = {dur}d. A duração NÃO é "
                          f"importada (vem do memorial: quantidade / produção / equipes) — ajuste no app se necessário.")
        if t["manual"] and t["inicio"]:
            dia = dia_util(t["inicio"])
            avisos.append(f"#{sid} {nome_subetapa(sub)}: tarefa agendada manualmente no Project — início "
                          f"{t['inicio']:%d/%m/%Y} importado como 'Não iniciar antes de'.")
        elif t["restricao"] in (2, 4) and t["data_restricao"]:
            dia = dia_util(t["data_restricao"])
        elif t["restricao"] in (3, 6) and t["data_restricao"]:
            dia = max(1, dia_util(t["data_restricao"]) - dur + 1)
        elif t["restricao"] == 0:
            dia = 1
        else:
            dia = sub.get("dia_inicio_planejado", 1)
            avisos.append(f"#{sid} {nome_subetapa(sub)}: restrição '{NOMES_RESTRICAO.get(t['restricao'], t['restricao'])}' "
                          f"não existe no app — dia de início mantido ({dia}).")
        if t["restricao"] in (2, 3):
            avisos.append(f"#{sid} {nome_subetapa(sub)}: '{NOMES_RESTRICAO[t['restricao']]}' importada como "
                          f"'Não iniciar antes de' (o app só tem esse tipo de restrição).")
        novos_dias[sid] = max(dia, inicio_resumo.get(sid, 1))

    # ---- 4. Aplica na cópia e registra as mudanças ----
    mudancas = []
    for sid in uid_para_sub.values():
        sub = sub_por_id[sid]
        antes_p = sorted(descrever_vinculo(v) for v in sub.get("predecessoras", []))
        depois_p = sorted(descrever_vinculo(v) for v in novas_preds[sid])
        antes_d, depois_d = sub.get("dia_inicio_planejado", 1), novos_dias[sid]
        if antes_p != depois_p or antes_d != depois_d:
            mudancas.append({"id": sid, "nome": nome_subetapa(sub), "preds": (antes_p, depois_p), "dia": (antes_d, depois_d)})
        sub["predecessoras"] = novas_preds[sid]
        sub["dia_inicio_planejado"] = depois_d

    fora = [f"#{sid} {nome_subetapa(t['sub'])}" for sid, t in subs_app.items() if sid not in uid_para_sub.values()]
    if fora:
        avisos.append("Subetapas do app que não estão no XML (mantidas sem alteração): " + ", ".join(fora))

    # ---- 5. Recalcula e compara com as datas do Project ----
    cron, resumo = calcular_cronograma(obras_novas, projeto_obj)  # levanta CicloDeVinculos se houver ciclo
    divergencias = []
    for t in tarefas_xml:
        sid = uid_para_sub.get(t["uid"])
        if sid is not None and t["inicio"] and cron[sid]["inicio"] != t["inicio"]:
            divergencias.append(f"#{sid} {nome_subetapa(sub_por_id[sid])}: Project {t['inicio']:%d/%m/%Y} | "
                                f"app {cron[sid]['inicio']:%d/%m/%Y}")

    return {
        "obras_novas": obras_novas,
        "mudancas": mudancas,
        "avisos": avisos,
        "divergencias": divergencias,
        "reconhecidas": len(uid_para_sub),
        "resumo": resumo,
    }


# ==============================================================================
# MENU INTERATIVO
# ==============================================================================

def importar_xml_project(projeto_obj, obras):
    """Seleciona o XML, mostra a prévia e grava (com backup) após confirmação. Retorna True se gravou."""
    limpar_terminal()
    print("=== IMPORTAR PREDECESSORAS E DATAS DO MS PROJECT ===\n")
    print("No Project: Arquivo > Salvar como > Formato XML (*.xml), na pasta do app.\n")
    xmls = sorted(f for f in os.listdir(DIRETORIO_ATUAL) if f.lower().endswith(".xml"))
    arq, _ = selecionar_item_lista(xmls + ["Informar outro caminho..."], titulo="Arquivo XML")
    if not arq:
        return False
    if arq == "Informar outro caminho...":
        caminho = input("\nCaminho completo do XML: ").strip().strip('"')
    else:
        caminho = os.path.join(DIRETORIO_ATUAL, arq)
    if not os.path.isfile(caminho):
        input("\n❌ Arquivo não encontrado. Pressione Enter...")
        return False

    try:
        plano = analisar_importacao(caminho, obras, projeto_obj)
    except CicloDeVinculos as e:
        input(f"\n❌ Importação recusada — {e}. Nada foi alterado. Pressione Enter...")
        return False
    except (ET.ParseError, ValueError) as e:
        input(f"\n❌ Não foi possível ler o XML: {e}. Nada foi alterado. Pressione Enter...")
        return False

    limpar_terminal()
    print(f"=== PRÉVIA DA IMPORTAÇÃO: {os.path.basename(caminho)} ===\n")
    print(f"Subetapas reconhecidas: {plano['reconhecidas']} | Com alteração: {len(plano['mudancas'])}")
    print(f"Novo término do projeto: {plano['resumo']['data_fim']:%d/%m/%Y} ({plano['resumo']['duracao']} dias úteis)\n")
    for m in plano["mudancas"]:
        print(f"  • #{m['id']} {m['nome']}")
        if m["preds"][0] != m["preds"][1]:
            print(f"      Predecessoras: {', '.join(m['preds'][0]) or '-'}  ->  {', '.join(m['preds'][1]) or '-'}")
        if m["dia"][0] != m["dia"][1]:
            print(f"      Dia de início planejado: {m['dia'][0]}  ->  {m['dia'][1]}")
    if plano["avisos"]:
        print("\n--- AVISOS ---")
        for a in plano["avisos"]:
            print(f"  ⚠️ {a}")
    if plano["divergencias"]:
        print("\n--- INÍCIO DIFERENTE DO PROJECT APÓS RECÁLCULO NO APP ---")
        for d in plano["divergencias"]:
            print(f"  • {d}")

    if not plano["mudancas"]:
        input("\nNenhuma alteração a importar. Pressione Enter...")
        return False
    if input("\nConfirma a importação? (S/N): ").strip().upper() != "S":
        input("\nImportação cancelada. Nada foi alterado. Pressione Enter...")
        return False

    backup = ARQUIVO_OBRAS.replace(".json", f"_backup_{datetime.now():%Y%m%d_%H%M%S}.json")
    shutil.copy2(ARQUIVO_OBRAS, backup)
    if salvar_obras(plano["obras_novas"]):
        input(f"\n✓ Importação concluída. Backup do estado anterior: {os.path.basename(backup)}. Pressione Enter...")
        return True
    input("\n❌ Falha ao salvar. Pressione Enter...")
    return False
