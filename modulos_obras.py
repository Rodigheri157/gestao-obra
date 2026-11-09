import math
import os
from modulos_agenda import (
    TIPOS_VINCULO,
    CicloDeVinculos,
    calcular_cronograma,
    descrever_vinculo,
    listar_subetapas_projeto,
)
from modulos_disc import carregar_disciplinas
from modulos_etapas import carregar_etapas
from modulos_geral import (
    pasta_do_app,
    carregar_json,
    confirmar,
    gerenciar_lista_ordenada,
    ler_float,
    ler_int,
    ler_inteiro,
    limpar_terminal,
    nome_subetapa,
    renomear_chave_mesclando,
    salvar_json,
    selecionar_item_lista,
)
from modulos_projetos import buscar_projeto, carregar_projetos

DIRETORIO_ATUAL = pasta_do_app()
ARQUIVO_OBRAS = os.path.join(DIRETORIO_ATUAL, "obras.json")


def carregar_obras():
    """Retorna a base de detalhamento de obras (atribui IDs às subetapas antigas que não tenham)."""
    dados = carregar_json(ARQUIVO_OBRAS, valor_padrao=[])
    obras = dados if isinstance(dados, list) else []
    if garantir_ids_subetapas(obras):
        salvar_obras(obras)
    return obras


def proximo_id_subetapa(obras, projeto_nome):
    """Próximo ID livre de subetapa dentro do projeto (os IDs são únicos por projeto)."""
    ids = listar_subetapas_projeto(obras, projeto_nome).keys()
    return max(ids, default=0) + 1


def garantir_ids_subetapas(obras):
    """Atribui 'id', 'predecessoras' e 'medicoes' às subetapas que ainda não possuem. Retorna True se alterou."""
    alterou = False
    for ob in obras:
        for etapas in ob.get("disciplinas", {}).values():
            for subs in etapas.values():
                for sub in subs:
                    if "id" not in sub:
                        sub["id"] = proximo_id_subetapa(obras, ob["projeto_nome"])
                        alterou = True
                    if "predecessoras" not in sub:
                        sub["predecessoras"] = []
                        alterou = True
                    if "medicoes" not in sub:
                        # Medição lançada antes do histórico: preservada como 'sem data'
                        executado = sub.get("quantidade_executada", 0.0)
                        sub["medicoes"] = [{"data": None, "acumulado": executado}] if executado > 0 else []
                        alterou = True
    return alterou


def ordenar_medicoes(sub):
    """Ordena o histórico: medições sem data primeiro (são anteriores ao histórico), depois por data."""
    sub["medicoes"].sort(key=lambda m: (m["data"] is not None, m["data"] or ""))


def atualizar_quantidade_executada(sub):
    """Quantidade executada atual = acumulado da medição mais recente do histórico."""
    ordenar_medicoes(sub)
    sub["quantidade_executada"] = sub["medicoes"][-1]["acumulado"] if sub["medicoes"] else 0.0


def limpar_vinculos_orfaos(obras, projeto_nome):
    """Remove vínculos que apontam para subetapas que não existem mais no projeto."""
    tarefas = listar_subetapas_projeto(obras, projeto_nome)
    for t in tarefas.values():
        t["sub"]["predecessoras"] = [v for v in t["sub"].get("predecessoras", []) if v["id"] in tarefas]


def salvar_obras(obras):
    """Salva a base de detalhamento de obras no JSON."""
    return salvar_json(ARQUIVO_OBRAS, obras)


def obter_ou_criar_obra(projeto_nome, area_nome, obra_nome):
    """Busca a obra no JSON ou cria sua estrutura inicial se for o primeiro acesso."""
    obras = carregar_obras()
    for ob in obras:
        if (
            ob.get("projeto_nome") == projeto_nome
            and ob.get("area_nome") == area_nome
            and ob.get("obra_nome") == obra_nome
        ):
            return ob, obras

    # Criação da estrutura de uma nova obra se ainda não existir no obras.json
    nova_obra_obj = {
        "projeto_nome": projeto_nome,
        "area_nome": area_nome,
        "obra_nome": obra_nome,
        "disciplinas": {}  # {"Civil": {"Fundação": [ subetapas_com_quantitativos ]}}
    }
    obras.append(nova_obra_obj)
    salvar_obras(obras)
    return nova_obra_obj, obras


def _eh_obra(ob, projeto_nome, area_nome, obra_nome):
    return (ob.get("projeto_nome") == projeto_nome and ob.get("area_nome") == area_nome
            and ob.get("obra_nome") == obra_nome)


def resumo_dados_obra(projeto_nome, area_nome, obra_nome):
    """Quantidade de subetapas já lançadas para a obra no obras.json (0 se não houver)."""
    for ob in carregar_obras():
        if _eh_obra(ob, projeto_nome, area_nome, obra_nome):
            return sum(len(subs) for etapas in ob.get("disciplinas", {}).values() for subs in etapas.values())
    return 0


def renomear_obra_cadastrada(projeto_nome, area_nome, nome_antigo, nome_novo):
    """Propaga a renomeação de uma obra (feita no cadastro do projeto) para o obras.json."""
    obras = carregar_obras()
    alterou = False
    for ob in obras:
        if _eh_obra(ob, projeto_nome, area_nome, nome_antigo):
            ob["obra_nome"] = nome_novo
            alterou = True
    return salvar_obras(obras) if alterou else True


def excluir_obra_cadastrada(projeto_nome, area_nome, obra_nome):
    """Apaga do obras.json o detalhamento da obra e os vínculos de outras obras que apontavam para ela."""
    obras = carregar_obras()
    restantes = [ob for ob in obras if not _eh_obra(ob, projeto_nome, area_nome, obra_nome)]
    if len(restantes) == len(obras):
        return True
    limpar_vinculos_orfaos(restantes, projeto_nome)
    return salvar_obras(restantes)


def resumo_dados_area(projeto_nome, area_nome):
    """Quantidade de obras com subetapas lançadas e total de subetapas da área no obras.json."""
    n_obras = n_subs = 0
    for ob in carregar_obras():
        if ob.get("projeto_nome") == projeto_nome and ob.get("area_nome") == area_nome:
            subs = sum(len(lst) for etapas in ob.get("disciplinas", {}).values() for lst in etapas.values())
            if subs:
                n_obras += 1
                n_subs += subs
    return n_obras, n_subs


def renomear_area_cadastrada(projeto_nome, nome_antigo, nome_novo):
    """Propaga a renomeação de uma área (feita no cadastro do projeto) para o obras.json."""
    obras = carregar_obras()
    alterou = False
    for ob in obras:
        if ob.get("projeto_nome") == projeto_nome and ob.get("area_nome") == nome_antigo:
            ob["area_nome"] = nome_novo
            alterou = True
    return salvar_obras(obras) if alterou else True


def excluir_area_cadastrada(projeto_nome, area_nome):
    """Apaga do obras.json todas as obras da área e os vínculos de outras obras que apontavam para elas."""
    obras = carregar_obras()
    restantes = [ob for ob in obras
                 if not (ob.get("projeto_nome") == projeto_nome and ob.get("area_nome") == area_nome)]
    if len(restantes) == len(obras):
        return True
    limpar_vinculos_orfaos(restantes, projeto_nome)
    return salvar_obras(restantes)


# ------------------------------------------------------------------------------
# Propagação de renomeações feitas nos catálogos (disciplina, etapa, subetapa, profissão).
# Cada função retorna quantas subetapas lançadas usam o nome antigo; com aplicar=True
# também renomeia e salva. (Os dados técnicos — unidade, produção, equipe — são copiados
# para a obra no lançamento e NÃO são alterados aqui.)
# ------------------------------------------------------------------------------

def _finalizar_propagacao(obras, n, aplicar):
    if aplicar and n:
        salvar_obras(obras)
    return n


def renomear_disciplina_nas_obras(antigo, novo, aplicar=True):
    obras, n = carregar_obras(), 0
    for ob in obras:
        discs = ob.get("disciplinas", {})
        if antigo in discs:
            n += sum(len(subs) for subs in discs[antigo].values())
            if aplicar:
                renomear_chave_mesclando(discs, antigo, novo)
    return _finalizar_propagacao(obras, n, aplicar)


def renomear_etapa_nas_obras(disciplina, antigo, novo, aplicar=True):
    obras, n = carregar_obras(), 0
    for ob in obras:
        etapas = ob.get("disciplinas", {}).get(disciplina, {})
        if antigo in etapas:
            n += len(etapas[antigo])
            if aplicar:
                renomear_chave_mesclando(etapas, antigo, novo)
    return _finalizar_propagacao(obras, n, aplicar)


def renomear_subetapa_nas_obras(disciplina, etapa, antigo, novo, aplicar=True):
    obras, n = carregar_obras(), 0
    for ob in obras:
        for sub in ob.get("disciplinas", {}).get(disciplina, {}).get(etapa, []):
            if sub.get("nome") == antigo:
                n += 1
                if aplicar:
                    sub["nome"] = novo
    return _finalizar_propagacao(obras, n, aplicar)


def renomear_profissao_nas_obras(disciplina, antigo, novo, aplicar=True):
    obras, n = carregar_obras(), 0
    for ob in obras:
        for subs in ob.get("disciplinas", {}).get(disciplina, {}).values():
            for sub in subs:
                equipe = sub.get("equipe_basica", {})
                if antigo in equipe:
                    n += 1
                    if aplicar:
                        renomear_chave_mesclando(equipe, antigo, novo)
    return _finalizar_propagacao(obras, n, aplicar)


def _escolher_etapa_catalogo(titulo):
    """Disciplina -> Etapa do catálogo. Retorna (disciplina, etapa_catalogo) ou (None, None)."""
    limpar_terminal()
    print(f"{titulo}\n")

    disciplinas = carregar_disciplinas()
    disc_sel, _ = selecionar_item_lista(disciplinas, titulo="Selecione a Disciplina")
    if not disc_sel:
        return None, None

    # Buscar etapas do catálogo filtradas pela disciplina selecionada
    etapas_catalogo = [e for e in carregar_etapas() if e.get("disciplina") == disc_sel]
    if not etapas_catalogo:
        print(f"\n❌ Nenhuma etapa cadastrada no catálogo para '{disc_sel}'.")
        input("\nPressione Enter para continuar...")
        return None, None

    etapa_cat_sel, _ = selecionar_item_lista(
        etapas_catalogo, titulo=f"Etapas do Catálogo ({disc_sel})", chave_nome="nome"
    )
    if not etapa_cat_sel:
        return None, None
    if not etapa_cat_sel.get("subetapas"):
        print("\n❌ Nenhuma subetapa disponível nesta etapa.")
        input("\nPressione Enter para continuar...")
        return None, None
    return disc_sel, etapa_cat_sel


def _lancar_subetapa(obra_obj, todas_obras, disc_sel, etapa_nome, sub_cat_sel,
                     qtd_fisica, equipes_padrao=1, dia_padrao=1):
    """
    Lê equipes, dia de início, complemento e observação, grava a subetapa na obra e
    retorna o registro lançado (ou None se não conseguiu salvar).
    """
    qtd_equipes = ler_int(f"Quantidade de Equipes Alocadas [{equipes_padrao}]: ", valor_padrao=equipes_padrao)
    dia_inicio = ler_int(f"Não iniciar antes do dia útil nº (do início do projeto) [{dia_padrao}]: ",
                         valor_padrao=dia_padrao)

    # Cálculo da duração em dias úteis
    prod_dia = sub_cat_sel.get("producao_equipe_dia", 1.0)
    if prod_dia > 0 and qtd_equipes > 0:
        duracao_calculada = math.ceil(qtd_fisica / (prod_dia * qtd_equipes))
    else:
        duracao_calculada = 1

    complemento = ler_complemento(sub_cat_sel["nome"], obra_obj, disc_sel, etapa_nome)
    obs = input("Observações para esta atividade (opcional): ").strip()

    subetapa_obra = {
        "id": proximo_id_subetapa(todas_obras, obra_obj["projeto_nome"]),
        "nome": sub_cat_sel["nome"],
        "complemento": complemento,
        "unidade": sub_cat_sel["unidade"],
        "quantidade_fisica": qtd_fisica,
        "producao_equipe_dia": prod_dia,
        "quantidade_equipes": qtd_equipes,
        "dia_inicio_planejado": dia_inicio,
        "duracao_dias_planejada": duracao_calculada,
        "quantidade_executada": 0.0,
        "equipe_basica": dict(sub_cat_sel.get("equipe_basica", {})),
        "observacao": obs,
        "predecessoras": [],
        "medicoes": []
    }

    # Estruturação no dicionário da obra (obra_obj é o mesmo objeto que está em todas_obras)
    lista_sub = obra_obj.setdefault("disciplinas", {}).setdefault(disc_sel, {}).setdefault(etapa_nome, [])
    lista_sub.append(subetapa_obra)

    if not salvar_obras(todas_obras):
        lista_sub.pop()
        if not lista_sub:
            del obra_obj["disciplinas"][disc_sel][etapa_nome]
        return None

    print(f"\n✓ Subetapa #{subetapa_obra['id']} '{nome_subetapa(subetapa_obra)}' ({qtd_fisica} {sub_cat_sel['unidade']}) adicionada!")
    print(f"✓ Duração Estimada: {duracao_calculada} dias úteis.")
    return subetapa_obra


def adicionar_subetapa_da_obra(obra_obj, todas_obras):
    """Vincular UMA subetapa do Catálogo à Obra informando a Quantidade Física específica."""
    disc_sel, etapa_cat_sel = _escolher_etapa_catalogo(
        f"--- VINCULAR SUBETAPA: {obra_obj['obra_nome'].upper()} ({obra_obj['area_nome']}) ---"
    )
    if not disc_sel:
        return

    sub_cat_sel, _ = selecionar_item_lista(
        etapa_cat_sel["subetapas"], titulo="Selecione a Subetapa", chave_nome="nome"
    )
    if not sub_cat_sel:
        return

    # Entrada do Quantitativo Físico Específico do Projeto/Obra
    limpar_terminal()
    print(f"Subetapa Selecionada: {sub_cat_sel['nome']}")
    print(f"Unidade Padrão: {sub_cat_sel['unidade']} | Rendimento: {sub_cat_sel['producao_equipe_dia']}/dia por equipe\n")

    qtd_fisica = ler_float(f"Digite a Quantidade Física Total em ({sub_cat_sel['unidade']}): ")
    _lancar_subetapa(obra_obj, todas_obras, disc_sel, etapa_cat_sel["nome"], sub_cat_sel, qtd_fisica)
    input("\nPressione Enter para continuar...")


def lancar_subetapas_em_sequencia(obra_obj, todas_obras):
    """
    Escolhida a etapa do catálogo, percorre suas subetapas na ordem cadastrada e lança uma
    após a outra, sem voltar ao menu. Em cada subetapa: Enter/S = lançar, N = pular,
    0 = encerrar. Equipes e dia de início do lançamento anterior viram o padrão do seguinte.
    Cada subetapa é salva assim que lançada (encerrar no meio não perde o que já foi feito).
    """
    disc_sel, etapa_cat_sel = _escolher_etapa_catalogo(
        f"--- LANÇAMENTO EM SEQUÊNCIA: {obra_obj['obra_nome'].upper()} ({obra_obj['area_nome']}) ---"
    )
    if not disc_sel:
        return

    etapa_nome = etapa_cat_sel["nome"]
    subs_cat = etapa_cat_sel["subetapas"]
    total = len(subs_cat)
    lancadas, puladas = [], []
    equipes_padrao, dia_padrao = 1, 1

    for pos, sub_cat in enumerate(subs_cat, 1):
        ja_lancadas = [
            s for s in obra_obj.get("disciplinas", {}).get(disc_sel, {}).get(etapa_nome, [])
            if s.get("nome") == sub_cat["nome"]
        ]

        limpar_terminal()
        print(f"=== LANÇAMENTO EM SEQUÊNCIA: {disc_sel} > {etapa_nome} ===")
        print(f"Obra: {obra_obj['obra_nome']} | Lançadas nesta sequência: {len(lancadas)} | Puladas: {len(puladas)}\n")
        print(f"[{pos}/{total}] {sub_cat['nome']}")
        print(f"      Unidade: {sub_cat.get('unidade', 'un')} | Rendimento: {sub_cat.get('producao_equipe_dia', 1.0)}/dia por equipe")
        if ja_lancadas:
            print(f"      ℹ️ Já lançada {len(ja_lancadas)}x nesta obra/etapa: "
                  + ", ".join(f"#{s['id']} {nome_subetapa(s)}" for s in ja_lancadas))

        resp = input("\nLançar esta subetapa? (Enter/S = sim | N = pular | 0 = encerrar): ").strip().upper()
        if resp == "0":
            puladas.extend(s["nome"] for s in subs_cat[pos - 1:])
            break
        if resp == "N":
            puladas.append(sub_cat["nome"])
            continue

        qtd_fisica = ler_float(f"Quantidade Física Total em ({sub_cat.get('unidade', 'un')}) [Enter/0 = pular]: ")
        if qtd_fisica <= 0:
            puladas.append(sub_cat["nome"])
            continue

        novo = _lancar_subetapa(obra_obj, todas_obras, disc_sel, etapa_nome, sub_cat, qtd_fisica,
                                equipes_padrao=equipes_padrao, dia_padrao=dia_padrao)
        if novo:
            lancadas.append(novo)
            equipes_padrao, dia_padrao = novo["quantidade_equipes"], novo["dia_inicio_planejado"]
        else:
            puladas.append(sub_cat["nome"])
        if pos < total:
            input("\nPressione Enter para ir à próxima subetapa...")

    # Resumo final
    limpar_terminal()
    print(f"=== RESUMO DO LANÇAMENTO: {disc_sel} > {etapa_nome} ===\n")
    if lancadas:
        print(f"✓ {len(lancadas)} subetapa(s) lançada(s):")
        for s in lancadas:
            print(f"     • #{s['id']} {nome_subetapa(s)}: {s['quantidade_fisica']} {s['unidade']} | "
                  f"Dur: {s['duracao_dias_planejada']}d")
    else:
        print("Nenhuma subetapa foi lançada.")
    if puladas:
        print(f"\n↷ {len(puladas)} não lançada(s): " + ", ".join(puladas))
    if len(lancadas) > 1:
        print("\nℹ️ As subetapas foram lançadas sem predecessoras. Para encadear as datas,")
        print("   use a opção 4 (Gerenciar Vínculos entre Atividades) do menu da obra.")
    input("\nPressione Enter para continuar...")


def ler_complemento(nome_catalogo, obra_obj, disciplina, etapa, ignorar=None):
    """
    Pede o complemento do nome (ex.: 'Blocos balança') que distingue lançamentos da mesma
    subetapa na mesma etapa. Mostra os já lançados e não aceita repetir um complemento já
    usado para a mesma subetapa na etapa. 'ignorar' = subetapa em edição (não conta como
    repetida); nesse caso Enter mantém o complemento atual e '-' remove o complemento.
    """
    existentes = [
        s for s in obra_obj.get("disciplinas", {}).get(disciplina, {}).get(etapa, [])
        if s.get("nome") == nome_catalogo and s is not ignorar
    ]
    usados = {(s.get("complemento") or "").strip().lower() for s in existentes}
    if existentes:
        print(f"\nℹ️ '{nome_catalogo}' já foi lançada {len(existentes)}x nesta etapa:")
        for s in existentes:
            print(f"     • #{s['id']} {nome_subetapa(s)}")
    print("\nComplemento do nome para distinguir a atividade (ex.: Blocos balança, Rampas de acesso).")
    while True:
        if ignorar is not None:
            comp = input(f"Complemento — ficará '{nome_catalogo} - <complemento>' "
                         "(Enter = manter; '-' = sem complemento): ").strip()
            if not comp:
                comp = ignorar.get("complemento") or ""
            elif comp == "-":
                comp = ""
        else:
            comp = input(f"Complemento — ficará '{nome_catalogo} - <complemento>' (Enter = sem complemento): ").strip()
        if comp.lower() in usados:
            print("⚠️ Esta subetapa já foi lançada nesta etapa com esse mesmo complemento. Informe outro.")
            continue
        return comp


def localizar_subetapa_na_obra(obra_obj, sub):
    """Retorna (disciplina, etapa) em que a subetapa está lançada na obra."""
    for disc, etapas in obra_obj.get("disciplinas", {}).items():
        for etapa, lista in etapas.items():
            if any(s is sub for s in lista):
                return disc, etapa
    return None, None


def calcular_duracao(qtd_fisica, prod_dia, qtd_equipes):
    """Duração em dias úteis = arred. p/ cima(quantidade / (produção por equipe/dia x equipes))."""
    if prod_dia > 0 and qtd_equipes > 0:
        return max(1, math.ceil(qtd_fisica / (prod_dia * qtd_equipes)))
    return 1


# Campos exibidos no resumo antes/depois da edição: (chave, rótulo)
_CAMPOS_EDITAVEIS = [
    ("quantidade_fisica", "Quantidade física"),
    ("producao_equipe_dia", "Produção/equipe/dia"),
    ("quantidade_equipes", "Equipes alocadas"),
    ("dia_inicio_planejado", "Não iniciar antes do dia"),
    ("duracao_dias_planejada", "Duração (dias úteis)"),
    ("complemento", "Complemento"),
    ("observacao", "Observação"),
]


def editar_subetapa(obra_obj, todas_obras):
    """
    Edita uma subetapa já lançada na obra: quantidade física, produção por equipe/dia,
    nº de equipes, dia de início, complemento do nome e observação. Enter mantém o valor
    atual de cada campo. A duração é recalculada e o cronograma é validado antes de salvar.
    """
    limpar_terminal()
    sub = selecionar_subetapa_da_obra(obra_obj, "Subetapa a editar")
    if not sub:
        return
    disc_sel, etapa_sel = localizar_subetapa_na_obra(obra_obj, sub)
    und = sub.get("unidade", "un")
    antes = {k: sub.get(k) for k, _ in _CAMPOS_EDITAVEIS}
    for k in ("complemento", "observacao"):
        antes[k] = antes[k] or ""

    limpar_terminal()
    print(f"--- EDITAR SUBETAPA #{sub['id']}: {nome_subetapa(sub).upper()} ---")
    print(f"{disc_sel} > {etapa_sel}")
    print(f"Executado até agora: {sub.get('quantidade_executada', 0.0)} {und}")
    print("(Enter = manter o valor atual)\n")

    qtd_atual = sub.get("quantidade_fisica", 0.0)
    qtd = ler_float(f"Quantidade física total em ({und}) [{qtd_atual}]: ", valor_padrao=qtd_atual)
    if qtd <= 0:
        print("⚠️ A quantidade deve ser maior que zero. Mantido o valor atual.")
        qtd = qtd_atual
    executado = sub.get("quantidade_executada", 0.0)
    if qtd < executado:
        print(f"⚠️ Atenção: a nova quantidade ({qtd} {und}) é menor que o já executado ({executado} {und}).")

    prod_atual = sub.get("producao_equipe_dia", 1.0)
    prod = ler_float(f"Produção por equipe/dia ({und}/dia) [{prod_atual}]: ", valor_padrao=prod_atual)
    if prod <= 0:
        print("⚠️ A produção deve ser maior que zero. Mantido o valor atual.")
        prod = prod_atual

    eqp_atual = sub.get("quantidade_equipes", 1)
    equipes = ler_int(f"Quantidade de equipes alocadas [{eqp_atual}]: ", valor_padrao=eqp_atual)

    dia_atual = sub.get("dia_inicio_planejado", 1)
    dia = ler_int(f"Não iniciar antes do dia útil nº (do início do projeto) [{dia_atual}]: ",
                  valor_padrao=dia_atual)

    print(f"\nComplemento atual: {sub.get('complemento') or '(nenhum)'}")
    comp = ler_complemento(sub["nome"], obra_obj, disc_sel, etapa_sel, ignorar=sub)
    print(f"\nObservação atual: {sub.get('observacao') or '(nenhuma)'}")
    obs = input("Nova observação (Enter = manter; '-' = apagar): ").strip()

    novos = {
        "quantidade_fisica": qtd,
        "producao_equipe_dia": prod,
        "quantidade_equipes": equipes,
        "dia_inicio_planejado": dia,
        "duracao_dias_planejada": calcular_duracao(qtd, prod, equipes),
        "complemento": comp,
        "observacao": "" if obs == "-" else (obs or sub.get("observacao", "")),
    }

    alterados = [(rot, antes[k], novos[k]) for k, rot in _CAMPOS_EDITAVEIS if antes[k] != novos[k]]
    if not alterados:
        print("\nNenhuma alteração informada.")
        input("\nPressione Enter para continuar...")
        return

    print("\nResumo das alterações:")
    for rot, de, para in alterados:
        print(f"     • {rot}: {de if de != '' else '(vazio)'} -> {para if para != '' else '(vazio)'}")
    if not confirmar("\nAplicar as alterações?"):
        input("\nPressione Enter para continuar...")
        return

    sub.update(novos)
    try:
        calcular_cronograma(todas_obras, buscar_projeto(obra_obj["projeto_nome"]))
    except (CicloDeVinculos, ValueError) as e:
        sub.update(antes)
        input(f"\n❌ Alteração recusada: {e}. Pressione Enter...")
        return

    if salvar_obras(todas_obras):
        print(f"\n✓ Subetapa #{sub['id']} '{nome_subetapa(sub)}' atualizada.")
        print("ℹ️ Se o cronograma já foi exportado para o MS Project, exporte de novo para atualizá-lo lá.")
    else:
        sub.update(antes)
    input("\nPressione Enter para continuar...")


def remover_etapa_da_obra(obra_obj, todas_obras):
    """Remove uma etapa completa de uma disciplina na obra."""
    limpar_terminal()
    disciplinas = obra_obj.get("disciplinas", {})
    if not disciplinas:
        print("❌ Nenhuma disciplina vinculada a esta obra.")
        input("\nPressione Enter para continuar...")
        return

    lista_disc = list(disciplinas.keys())
    disc_sel, _ = selecionar_item_lista(lista_disc, titulo="Selecione a Disciplina")
    if not disc_sel:
        return

    etapas_dict = disciplinas[disc_sel]
    if not etapas_dict:
        print(f"\n❌ Nenhuma etapa encontrada em '{disc_sel}'.")
        input("\nPressione Enter para continuar...")
        return

    lista_etapas = list(etapas_dict.keys())
    etapa_sel, _ = selecionar_item_lista(lista_etapas, titulo=f"Etapas na Obra ({disc_sel})")
    if not etapa_sel:
        return

    confirma = input(f"\n⚠️ Remover a etapa '{etapa_sel}' e todas as suas subetapas? (S/N): ").strip().upper()
    if confirma == "S":
        del obra_obj["disciplinas"][disc_sel][etapa_sel]
        limpar_vinculos_orfaos(todas_obras, obra_obj["projeto_nome"])
        salvar_obras(todas_obras)
        print(f"\n✓ Etapa '{etapa_sel}' removida com sucesso!")

    input("\nPressione Enter para continuar...")


def remover_subetapa_da_obra(obra_obj, todas_obras):
    """Remove uma subetapa lançada na obra (e os vínculos de outras atividades com ela)."""
    limpar_terminal()
    sub = selecionar_subetapa_da_obra(obra_obj, "Subetapa a remover")
    if not sub:
        return

    # Localiza disciplina/etapa da subetapa escolhida
    disc_sel, etapa_sel = localizar_subetapa_na_obra(obra_obj, sub)

    # Avisa sobre medições e atividades que dependem dela
    tarefas = listar_subetapas_projeto(todas_obras, obra_obj["projeto_nome"])
    dependentes = [
        t["sub"] for t in tarefas.values()
        if any(v["id"] == sub["id"] for v in t["sub"].get("predecessoras", []))
    ]
    if sub.get("medicoes"):
        print(f"\n⚠️ A subetapa tem {len(sub['medicoes'])} medição(ões) registrada(s), que serão apagadas.")
    if dependentes:
        print(f"⚠️ {len(dependentes)} atividade(s) têm esta subetapa como predecessora; esses vínculos serão removidos:")
        for d in dependentes:
            print(f"     • #{d['id']} {nome_subetapa(d)}")

    if not confirmar(f"\nRemover a subetapa #{sub['id']} '{nome_subetapa(sub)}' ({disc_sel} > {etapa_sel})?"):
        input("\nPressione Enter para continuar...")
        return

    lista = obra_obj["disciplinas"][disc_sel][etapa_sel]
    lista[:] = [s for s in lista if s is not sub]
    if not lista:
        del obra_obj["disciplinas"][disc_sel][etapa_sel]
        print(f"\n(A etapa '{etapa_sel}' ficou vazia e foi removida da obra.)")

    limpar_vinculos_orfaos(todas_obras, obra_obj["projeto_nome"])
    if salvar_obras(todas_obras):
        print(f"\n✓ Subetapa #{sub['id']} '{nome_subetapa(sub)}' removida com sucesso!")
    input("\nPressione Enter para continuar...")


def selecionar_subetapa_da_obra(obra_obj, titulo):
    """Lista as subetapas da obra (com ID) e retorna a escolhida, ou None."""
    subs = [
        (disc, etapa, sub)
        for disc, etapas in obra_obj.get("disciplinas", {}).items()
        for etapa, lista in etapas.items()
        for sub in lista
    ]
    rotulos = [f"#{sub['id']} {disc} > {etapa} > {nome_subetapa(sub)}" for disc, etapa, sub in subs]
    escolhido, idx = selecionar_item_lista(rotulos, titulo=titulo)
    return subs[idx][2] if escolhido else None


def gerenciar_vinculos(obra_obj, todas_obras):
    """Cadastra/remove predecessoras de uma subetapa (podem ser de qualquer obra do projeto)."""
    limpar_terminal()
    sub = selecionar_subetapa_da_obra(obra_obj, "Subetapa que receberá os vínculos")
    if not sub:
        return

    projeto = buscar_projeto(obra_obj["projeto_nome"])
    while True:
        limpar_terminal()
        tarefas = listar_subetapas_projeto(todas_obras, obra_obj["projeto_nome"])
        print(f"=== PREDECESSORAS DE #{sub['id']} {nome_subetapa(sub).upper()} ===\n")
        if not sub["predecessoras"]:
            print("  └── (Sem predecessoras: inicia no início do projeto ou na restrição de dia)")
        for idx, v in enumerate(sub["predecessoras"], 1):
            pred = tarefas[v["id"]]
            print(f"  {idx}. {descrever_vinculo(v)} → {pred['obra']['obra_nome']} > {pred['etapa']} > {nome_subetapa(pred['sub'])}")

        print("\n" + "-" * 50)
        print("1. Adicionar Predecessora")
        print("2. Remover Predecessora")
        print("0. Voltar\n")
        op = input("Escolha uma opção: ").strip()

        if op == "1":
            limpar_terminal()
            obras_proj = [ob for ob in todas_obras
                          if ob["projeto_nome"] == obra_obj["projeto_nome"] and ob.get("disciplinas")]
            rotulos = [f"{ob['area_nome']} > {ob['obra_nome']}" for ob in obras_proj]
            ob_sel, idx_ob = selecionar_item_lista(rotulos, titulo="Obra da predecessora")
            if not ob_sel:
                continue
            limpar_terminal()
            pred = selecionar_subetapa_da_obra(obras_proj[idx_ob], "Subetapa predecessora")
            if not pred:
                continue
            if pred["id"] == sub["id"] or any(v["id"] == pred["id"] for v in sub["predecessoras"]):
                input("\n⚠️ Vínculo inválido ou já existente. Pressione Enter...")
                continue

            print("\nTipo de vínculo:")
            siglas = list(TIPOS_VINCULO)
            for i, sigla in enumerate(siglas, 1):
                print(f"  {i}. {sigla} - {TIPOS_VINCULO[sigla]}")
            n = input("Escolha o tipo [1]: ").strip() or "1"
            tipo = siglas[int(n) - 1] if n.isdigit() and 1 <= int(n) <= len(siglas) else "TI"
            lag = ler_inteiro("Defasagem em dias úteis (+ espera / - sobreposição) [0]: ", valor_padrao=0)

            sub["predecessoras"].append({"id": pred["id"], "tipo": tipo, "lag_dias": lag})
            try:
                calcular_cronograma(todas_obras, projeto)
            except (CicloDeVinculos, ValueError) as e:
                sub["predecessoras"].pop()
                input(f"\n❌ Vínculo recusado: {e}. Pressione Enter...")
                continue
            salvar_obras(todas_obras)
            input(f"\n✓ Vínculo {descrever_vinculo(sub['predecessoras'][-1])} adicionado! Pressione Enter...")

        elif op == "2":
            rotulos = [descrever_vinculo(v) for v in sub["predecessoras"]]
            v_sel, idx_v = selecionar_item_lista(rotulos, titulo="Remover Predecessora")
            if v_sel:
                sub["predecessoras"].pop(idx_v)
                salvar_obras(todas_obras)

        elif op == "0":
            break


def _reordenar_chaves(dicionario, titulo, rotulo, ao_salvar):
    """Reordena as chaves de um dicionário (disciplinas/etapas) usando o menu de lista ordenada."""
    chaves = list(dicionario.keys())

    def aplicar():
        itens = {k: dicionario[k] for k in chaves}
        dicionario.clear()
        dicionario.update(itens)
        ao_salvar()

    gerenciar_lista_ordenada(chaves, titulo, rotulo=rotulo, ao_alterar=aplicar, permite_remover=False)


def reordenar_eap_obra(obra_obj, todas_obras):
    """
    Reorganiza a sequência da EAP da obra (disciplinas, etapas e subetapas).
    A ordem define como a EAP aparece na tela, no memorial, nos relatórios e na
    exportação para o MS Project; as DATAS continuam vindo dos vínculos e da
    restrição 'não iniciar antes do dia'.
    """
    def salvar():
        salvar_obras(todas_obras)

    while True:
        limpar_terminal()
        print(f"=== REORGANIZAR EAP: {obra_obj['obra_nome'].upper()} ===\n")
        disciplinas = obra_obj.get("disciplinas", {})
        if not disciplinas:
            print("❌ Nenhuma disciplina vinculada a esta obra.")
            input("\nPressione Enter para continuar...")
            return

        for disc, etapas in disciplinas.items():
            print(f"  [{disc.upper()}]")
            for etapa_nome, subs in etapas.items():
                print(f"    └── {etapa_nome}")
                for sub in subs:
                    print(f"          • #{sub['id']} {nome_subetapa(sub)}")

        print("\n" + "-" * 60)
        print("1. Reordenar Subetapas dentro de uma Etapa")
        print("2. Reordenar Etapas dentro de uma Disciplina")
        print("3. Reordenar Disciplinas")
        print("0. Voltar\n")
        print("ℹ️ A ordem muda a sequência da EAP (tela, relatórios e MS Project). Para mudar")
        print("   as datas, ajuste as predecessoras (opção 4 do menu da obra).\n")
        op = input("Escolha uma opção: ").strip()

        if op == "1":
            limpar_terminal()
            pares = [(d, e) for d, etapas in disciplinas.items() for e in etapas]
            rotulos = [f"{d} > {e} ({len(disciplinas[d][e])} subetapa(s))" for d, e in pares]
            sel, idx = selecionar_item_lista(rotulos, titulo="Etapa a reorganizar")
            if sel:
                d, e = pares[idx]
                gerenciar_lista_ordenada(
                    disciplinas[d][e], f"Subetapas de {d} > {e}",
                    rotulo=lambda s: f"#{s['id']} {nome_subetapa(s)}",
                    ao_alterar=salvar, permite_remover=False,
                )
        elif op == "2":
            limpar_terminal()
            disc_sel, _ = selecionar_item_lista(list(disciplinas.keys()), titulo="Disciplina")
            if disc_sel:
                etapas = disciplinas[disc_sel]
                _reordenar_chaves(etapas, f"Etapas de {disc_sel}",
                                  lambda e: f"{e} ({len(etapas[e])} subetapa(s))", salvar)
        elif op == "3":
            _reordenar_chaves(disciplinas, "Disciplinas da obra", str, salvar)
        elif op == "0":
            break


def detalhar_obra(obra_obj, todas_obras):
    """Exibe o EAP detalhado da obra e menu de ações executivas."""
    while True:
        limpar_terminal()
        print(f"=== DETALHAMENTO DA OBRA: {obra_obj['obra_nome'].upper()} ===")
        print(f"Projeto: {obra_obj['projeto_nome']} | Área: {obra_obj['area_nome']}")

        cron, resumo = {}, None
        try:
            cron, resumo = calcular_cronograma(todas_obras, buscar_projeto(obra_obj["projeto_nome"]))
            if resumo["aviso"]:
                print(resumo["aviso"])
        except (CicloDeVinculos, ValueError) as e:
            print(f"⚠️ Cronograma não calculado: {e}")
        print()

        disciplinas = obra_obj.get("disciplinas", {})
        if not disciplinas:
            print("  └── (Nenhum quantitativo físico cadastrado nesta obra)")
        else:
            for disc, etapas in disciplinas.items():
                print(f"  [DISCIPLINA: {disc.upper()}]")
                for etapa_nome, subetapas in etapas.items():
                    print(f"    └── Etapa: {etapa_nome}")
                    for sub in subetapas:
                        qtd = sub.get("quantidade_fisica", 0.0)
                        und = sub.get("unidade", "un")
                        dur = sub.get("duracao_dias_planejada", 0)
                        eqp = ", ".join([f"{k}:{v}" for k, v in sub.get("equipe_basica", {}).items()])
                        c = cron.get(sub["id"])
                        datas = f"{c['inicio']:%d/%m/%y} a {c['termino']:%d/%m/%y}" if c else "datas n/d"
                        preds = ", ".join(descrever_vinculo(v) for v in sub.get("predecessoras", [])) or "-"
                        print(
                            f"          • #{sub['id']} {nome_subetapa(sub)}: {qtd} {und} | {datas} | Dur: {dur}d | Pred: {preds} | Eqp: [{eqp}]"
                        )

        print("\n" + "-" * 60)
        print("1. Adicionar Subetapa do Catálogo (Lançar Quantitativo)")
        print("2. Remover Subetapa da Obra")
        print("3. Remover Etapa da Obra")
        print("4. Gerenciar Vínculos entre Atividades (Predecessoras)")
        print("5. Reorganizar Sequência da EAP (Etapas e Subetapas)")
        print("6. Editar Subetapa (Quantidade, Produção, Equipes, Início, Nome, Observação)")
        print("7. Lançar Subetapas de uma Etapa em Sequência")
        print("0. Voltar\n")

        op = input("Escolha uma opção: ").strip()

        if op == "1":
            adicionar_subetapa_da_obra(obra_obj, todas_obras)
        elif op == "2":
            remover_subetapa_da_obra(obra_obj, todas_obras)
        elif op == "3":
            remover_etapa_da_obra(obra_obj, todas_obras)
        elif op == "4":
            gerenciar_vinculos(obra_obj, todas_obras)
        elif op == "5":
            reordenar_eap_obra(obra_obj, todas_obras)
        elif op == "6":
            editar_subetapa(obra_obj, todas_obras)
        elif op == "7":
            lancar_subetapas_em_sequencia(obra_obj, todas_obras)
        elif op == "0":
            break


def menu_obras():
    """Navegação hierárquica: Projetos -> Áreas -> Obras -> EAP Executivo."""
    while True:
        limpar_terminal()
        projetos = carregar_projetos()

        if not projetos:
            print("❌ Nenhum projeto cadastrado no sistema.")
            print("Por favor, cadastre um projeto e suas áreas antes de acessar a gestão de obras.")
            input("\nPressione Enter para continuar...")
            break

        proj_sel, _ = selecionar_item_lista(projetos, titulo="Selecione o Projeto", chave_nome="nome")
        if not proj_sel:
            break

        areas_dict = proj_sel.get("areas", {})
        if not areas_dict:
            print(f"\n❌ O projeto '{proj_sel['nome']}' não possui áreas cadastradas.")
            input("\nPressione Enter para continuar...")
            continue

        area_sel, _ = selecionar_item_lista(list(areas_dict.keys()), titulo="Selecione a Área")
        if not area_sel:
            continue

        obras_lista = areas_dict[area_sel]
        if not obras_lista:
            print(f"\n❌ A área '{area_sel}' não possui obras cadastradas.")
            input("\nPressione Enter para continuar...")
            continue

        obra_nome_sel, _ = selecionar_item_lista(obras_lista, titulo=f"Obras em '{area_sel}'")
        if not obra_nome_sel:
            continue

        # Carrega/Instancia o objeto da obra real
        obra_obj, todas_obras = obter_ou_criar_obra(proj_sel["nome"], area_sel, obra_nome_sel)
        detalhar_obra(obra_obj, todas_obras)