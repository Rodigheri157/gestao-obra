import os
from modulos_disc import carregar_disciplinas
from modulos_geral import (
    pasta_do_app,
    carregar_json,
    confirmar,
    gerenciar_lista_ordenada,
    ler_float,
    limpar_terminal,
    propagar_para_obras,
    salvar_json,
    selecionar_item_lista,
)
from modulos_profissoes import obter_profissoes_por_disciplina

DIRETORIO_ATUAL = pasta_do_app()
ARQUIVO_ETAPAS = os.path.join(DIRETORIO_ATUAL, "etapas.json")


def carregar_etapas():
    """Retorna o catálogo global de etapas."""
    dados = carregar_json(ARQUIVO_ETAPAS, valor_padrao=[])
    return dados if isinstance(dados, list) else []


def salvar_etapas(etapas):
    """Salva o catálogo global de etapas no JSON."""
    return salvar_json(ARQUIVO_ETAPAS, etapas)


def cad_etapa(disciplina_selecionada):
    """Cadastra uma nova etapa vinculada à disciplina selecionada."""
    limpar_terminal()
    print(f"--- NOVA ETAPA ({disciplina_selecionada.upper()}) ---\n")

    nova_etapa = input("Digite o nome da nova etapa: ").strip().title()
    if not nova_etapa:
        print("\n❌ Nome de etapa inválido!")
        input("\nPressione Enter para continuar...")
        return

    etapas = carregar_etapas()

    # Verifica duplicidade na mesma disciplina
    existe = any(
        e.get("nome", "").lower() == nova_etapa.lower()
        and e.get("disciplina", "").lower() == disciplina_selecionada.lower()
        for e in etapas
    )

    if existe:
        print(f"\n⚠️ A etapa '{nova_etapa}' já existe em '{disciplina_selecionada}'!")
    else:
        etapas.append({
            "nome": nova_etapa,
            "disciplina": disciplina_selecionada,
            "subetapas": []
        })
        if salvar_etapas(etapas):
            print(f"\n✓ Etapa '{nova_etapa}' cadastrada com sucesso!")

    input("\nPressione Enter para continuar...")


def editar_equipe_basica(equipe, disciplina, nome_sub):
    """Monta/ajusta a equipe básica (altera 'equipe' no lugar). Quantidade 0 retira o profissional."""
    profissoes = obter_profissoes_por_disciplina(disciplina)
    if not profissoes:
        print(f"\n⚠️ Não há profissões cadastradas para '{disciplina}'. A equipe não pode ser alterada.")
        input("\nPressione Enter para continuar...")
        return

    while True:
        limpar_terminal()
        print(f"Subetapa: {nome_sub} | Disciplina: {disciplina}")
        print("Composição atual da equipe básica:")
        if not equipe:
            print("  └── (Nenhum profissional adicionado)")
        else:
            for prof, qtd in equipe.items():
                print(f"  • {prof}: {qtd}")
        print()

        prof_sel, _ = selecionar_item_lista(
            profissoes, titulo=f"Profissões Disponíveis ({disciplina}) — 0 para concluir"
        )
        if not prof_sel:
            break

        atual = equipe.get(prof_sel, 0)
        qtd_p = ler_float(f"Quantidade de '{prof_sel}' na equipe (0 retira) [{atual}]: ", valor_padrao=atual)
        if qtd_p > 0:
            equipe[prof_sel] = int(qtd_p)
        else:
            equipe.pop(prof_sel, None)


def _nome_sub_duplicado(etapa_obj, nome, ignorar=None):
    return any(
        s is not ignorar and s.get("nome", "").lower() == nome.lower()
        for s in etapa_obj.get("subetapas", [])
    )


def cad_subetapa_catalogo(etapa_obj, todas_etapas, idx_etapa):
    """Cadastra uma nova subetapa no catálogo com índices operacionais e equipe básica."""
    limpar_terminal()
    disc_etapa = etapa_obj.get("disciplina", "Geral")

    print(f"--- NOVA SUBETAPA EM: {etapa_obj['nome'].upper()} ({disc_etapa.upper()}) ---\n")

    nome_sub = input("Nome da Subetapa: ").strip().title()
    if not nome_sub:
        print("\n❌ Nome inválido.")
        input("\nPressione Enter para continuar...")
        return
    if _nome_sub_duplicado(etapa_obj, nome_sub):
        print(f"\n⚠️ A subetapa '{nome_sub}' já existe nesta etapa.")
        input("\nPressione Enter para continuar...")
        return

    unidade = input("Unidade de Medida (ex: m, m³, kg, un) [un]: ").strip()
    if not unidade:
        unidade = "un"

    producao_dia = ler_float("Produção por Equipe/Dia (ex: 25.0) [1.0]: ", valor_padrao=1.0)

    # Composição da Equipe Básica
    equipe_basica = {}
    editar_equipe_basica(equipe_basica, disc_etapa, nome_sub)

    subetapa_catalogo = {
        "nome": nome_sub,
        "unidade": unidade,
        "producao_equipe_dia": producao_dia,
        "equipe_basica": equipe_basica
    }

    if "subetapas" not in etapa_obj or not isinstance(etapa_obj["subetapas"], list):
        etapa_obj["subetapas"] = []

    etapa_obj["subetapas"].append(subetapa_catalogo)
    todas_etapas[idx_etapa] = etapa_obj

    if salvar_etapas(todas_etapas):
        print(f"\n✓ Subetapa '{nome_sub}' cadastrada no catálogo!")
    input("\nPressione Enter para continuar...")


def descrever_subetapa(sub):
    """Linha-resumo de uma subetapa do catálogo."""
    und = sub.get("unidade", "un")
    prod = sub.get("producao_equipe_dia", 1.0)
    eqp = ", ".join(f"{k}:{v}" for k, v in sub.get("equipe_basica", {}).items()) or "Sem equipe"
    return f"{sub.get('nome', 'Sem Nome')} ({und}) | Prod: {prod}/dia | Equipe: [{eqp}]"


def editar_subetapa_catalogo(sub, etapa_obj):
    """Edita nome, unidade, produção e equipe de uma subetapa do catálogo. Retorna a subetapa alterada ou None."""
    # Import local: modulos_obras já importa este módulo (evita importação circular)
    from modulos_obras import renomear_subetapa_nas_obras

    disc = etapa_obj.get("disciplina", "Geral")
    limpar_terminal()
    print(f"--- EDITAR SUBETAPA: {sub['nome'].upper()} ---")
    print("(Enter mantém o valor atual)\n")

    nome = input(f"Nome [{sub['nome']}]: ").strip().title() or sub["nome"]
    if nome != sub["nome"] and _nome_sub_duplicado(etapa_obj, nome, ignorar=sub):
        input(f"\n⚠️ Já existe a subetapa '{nome}' nesta etapa. Pressione Enter...")
        return None

    und_atual = sub.get("unidade", "un")
    unidade = input(f"Unidade de Medida [{und_atual}]: ").strip() or und_atual
    prod_atual = sub.get("producao_equipe_dia", 1.0)
    producao = ler_float(f"Produção por Equipe/Dia [{prod_atual}]: ", valor_padrao=prod_atual)

    novo = dict(sub, nome=nome, unidade=unidade, producao_equipe_dia=producao,
                equipe_basica=dict(sub.get("equipe_basica", {})))
    if confirmar("\nAlterar a composição da equipe básica?"):
        editar_equipe_basica(novo["equipe_basica"], disc, nome)

    if novo == sub:
        return None

    mostrou = False
    if nome != sub["nome"]:
        mostrou = propagar_para_obras(
            renomear_subetapa_nas_obras, (disc, etapa_obj["nome"], sub["nome"], nome),
            f"a subetapa '{sub['nome']}'",
        )
    if (unidade, producao, novo["equipe_basica"]) != (und_atual, prod_atual, sub.get("equipe_basica", {})):
        print("\nℹ️ Unidade, produção e equipe são copiadas para a obra no lançamento:")
        print("   as subetapas já lançadas nas obras mantêm os valores anteriores.")
        mostrou = True
    if mostrou:
        input("\nPressione Enter para continuar...")
    return novo


def gerenciar_subetapas_catalogo(etapa_obj, todas_etapas, idx_etapa):
    """Sub-menu para visualizar, adicionar, editar, remover e reordenar subetapas do catálogo."""
    while True:
        limpar_terminal()
        print(f"=== ETAPA: {etapa_obj['nome'].upper()} ({etapa_obj.get('disciplina', '').upper()}) ===\n")

        subetapas = etapa_obj.setdefault("subetapas", [])
        if not subetapas:
            print("  └── (Nenhuma subetapa cadastrada nesta etapa)")
        else:
            for idx, sub in enumerate(subetapas, 1):
                print(f"  {idx}. {descrever_subetapa(sub)}")

        print("\n" + "-" * 50)
        print("1. Adicionar Subetapa")
        print("2. Editar / Remover / Reordenar Subetapas")
        print("0. Voltar\n")

        op = input("Escolha uma opção: ").strip()

        if op == "1":
            cad_subetapa_catalogo(etapa_obj, todas_etapas, idx_etapa)
        elif op == "2":
            def remover(sub):
                print("\n(As subetapas já lançadas nas obras não são alteradas.)")
                return confirmar(f"Remover a subetapa '{sub['nome']}' do catálogo?")

            gerenciar_lista_ordenada(
                subetapas,
                titulo=f"Subetapas da etapa '{etapa_obj['nome']}'",
                rotulo=descrever_subetapa,
                editar=lambda sub: editar_subetapa_catalogo(sub, etapa_obj),
                remover=remover,
                ao_alterar=lambda: salvar_etapas(todas_etapas),
            )
        elif op == "0":
            break


def editar_remover_reordenar_etapas(disciplina, todas_etapas):
    """Editar, remover e reordenar as etapas de uma disciplina no catálogo."""
    # Import local: modulos_obras já importa este módulo (evita importação circular)
    from modulos_obras import renomear_etapa_nas_obras

    etapas_disc = [et for et in todas_etapas if et.get("disciplina") == disciplina]

    def editar(et):
        antigo = et["nome"]
        novo = input(f"\nNovo nome para a etapa '{antigo}' [Enter para cancelar]: ").strip().title()
        if not novo or novo == antigo:
            return None
        if any(e is not et and e.get("nome", "").lower() == novo.lower() for e in etapas_disc):
            input(f"\n⚠️ Já existe a etapa '{novo}' em '{disciplina}'. Pressione Enter...")
            return None
        et["nome"] = novo
        if propagar_para_obras(renomear_etapa_nas_obras, (disciplina, antigo, novo), f"a etapa '{antigo}'"):
            input("\nPressione Enter para continuar...")
        return et

    def remover(et):
        n_subs = len(et.get("subetapas", []))
        if n_subs:
            print(f"\n⚠️ A etapa '{et['nome']}' tem {n_subs} subetapa(s) no catálogo, que também serão removidas.")
        print("   (As subetapas já lançadas nas obras não são alteradas.)")
        return confirmar(f"\nRemover a etapa '{et['nome']}'?")

    def ao_alterar():
        # Recoloca as etapas da disciplina (na nova ordem) no lugar delas na lista global
        pos = next((i for i, e in enumerate(todas_etapas) if e.get("disciplina") == disciplina), len(todas_etapas))
        outras = [e for e in todas_etapas if e.get("disciplina") != disciplina]
        todas_etapas[:] = outras[:pos] + etapas_disc + outras[pos:]
        salvar_etapas(todas_etapas)

    gerenciar_lista_ordenada(
        etapas_disc,
        titulo=f"Etapas do catálogo: {disciplina}",
        rotulo=lambda et: f"{et['nome']} ({len(et.get('subetapas', []))} subetapas)",
        editar=editar,
        remover=remover,
        ao_alterar=ao_alterar,
    )


def menu_etapas():
    """Menu principal do catálogo de etapas filtrado por disciplina."""
    while True:
        limpar_terminal()
        disciplinas = carregar_disciplinas()
        if not disciplinas:
            print("❌ Nenhuma disciplina cadastrada no sistema.")
            input("\nPressione Enter para continuar...")
            break

        disc_sel, _ = selecionar_item_lista(disciplinas, titulo="Selecione a Disciplina")
        if not disc_sel:
            break

        # Sub-loop de etapas da disciplina escolhida
        while True:
            limpar_terminal()
            todas_etapas = carregar_etapas()

            # Filtra e guarda índice original
            etapas_filtradas = [
                (idx, et) for idx, et in enumerate(todas_etapas)
                if et.get("disciplina") == disc_sel
            ]

            print(f"=== ETAPAS DO CATÁLOGO: {disc_sel.upper()} ===\n")
            if not etapas_filtradas:
                print("  └── (Nenhuma etapa cadastrada nesta disciplina)")
            else:
                for pos, (idx_orig, et) in enumerate(etapas_filtradas, 1):
                    tot_sub = len(et.get("subetapas", []))
                    print(f"  {pos}. {et['nome']} ({tot_sub} subetapas)")

            print("\n" + "-" * 50)
            print("1. Cadastrar Nova Etapa")
            print("2. Gerenciar Subetapas de uma Etapa (adicionar / editar / remover / reordenar)")
            print("3. Editar / Remover / Reordenar Etapas")
            print("0. Selecionar Outra Disciplina\n")

            op = input("Escolha uma opção: ").strip()

            if op == "1":
                cad_etapa(disc_sel)

            elif op == "2":
                if not etapas_filtradas:
                    input("\n❌ Nenhuma etapa para gerenciar. Pressione Enter...")
                    continue
                n = input("\nNúmero da etapa a gerenciar: ").strip()
                if n.isdigit() and 1 <= int(n) <= len(etapas_filtradas):
                    idx_orig = etapas_filtradas[int(n) - 1][0]
                    gerenciar_subetapas_catalogo(todas_etapas[idx_orig], todas_etapas, idx_orig)

            elif op == "3":
                editar_remover_reordenar_etapas(disc_sel, todas_etapas)

            elif op == "0":
                break
