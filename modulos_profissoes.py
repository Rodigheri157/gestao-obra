import os
from modulos_disc import carregar_disciplinas
from modulos_geral import (
    pasta_do_app,
    carregar_json,
    confirmar,
    gerenciar_lista_ordenada,
    limpar_terminal,
    propagar_para_obras,
    renomear_chave_mesclando,
    salvar_json,
    selecionar_item_lista,
)

DIRETORIO_ATUAL = pasta_do_app()
ARQUIVO_PROFISSOES = os.path.join(DIRETORIO_ATUAL, "profissoes.json")


def carregar_profissoes():
    """Retorna o dicionário de profissões por disciplina."""
    dados = carregar_json(ARQUIVO_PROFISSOES, valor_padrao={})
    return dados if isinstance(dados, dict) else {}


def salvar_profissoes(profissoes_dict):
    """Salva o dicionário de profissões no JSON."""
    return salvar_json(ARQUIVO_PROFISSOES, profissoes_dict)


def obter_profissoes_por_disciplina(disciplina_nome):
    """Retorna a lista de profissões associadas à disciplina indicada."""
    profissoes_dict = carregar_profissoes()
    return profissoes_dict.get(disciplina_nome, [])


def _subetapas_catalogo_da_disciplina(etapas, disciplina):
    """Subetapas do catálogo de etapas pertencentes à disciplina."""
    return [sub for et in etapas if et.get("disciplina") == disciplina for sub in et.get("subetapas", [])]


def editar_remover_reordenar_profissoes(disciplina, profissoes_dict):
    """Editar, remover e reordenar as profissões de uma disciplina (propaga para as equipes básicas)."""
    # Imports locais: esses módulos já importam este (evita importação circular)
    from modulos_etapas import carregar_etapas, salvar_etapas
    from modulos_obras import renomear_profissao_nas_obras

    lista = profissoes_dict.setdefault(disciplina, [])

    def editar(nome_atual):
        novo = input(f"\nNovo nome para a profissão '{nome_atual}' [Enter para cancelar]: ").strip().title()
        if not novo or novo == nome_atual:
            return None
        if novo in lista:
            input("\n⚠️ Já existe uma profissão com esse nome nesta disciplina. Pressione Enter...")
            return None

        # Equipes básicas do catálogo acompanham a renomeação
        etapas = carregar_etapas()
        usos = [s for s in _subetapas_catalogo_da_disciplina(etapas, disciplina) if nome_atual in s.get("equipe_basica", {})]
        for sub in usos:
            renomear_chave_mesclando(sub["equipe_basica"], nome_atual, novo)
        if usos:
            salvar_etapas(etapas)

        if propagar_para_obras(renomear_profissao_nas_obras, (disciplina, nome_atual, novo),
                               f"a profissão '{nome_atual}' na equipe básica"):
            input("\nPressione Enter para continuar...")
        return novo

    def remover(nome):
        etapas = carregar_etapas()
        usos = [s for s in _subetapas_catalogo_da_disciplina(etapas, disciplina) if nome in s.get("equipe_basica", {})]
        if usos:
            print(f"\n⚠️ A profissão '{nome}' faz parte da equipe básica de {len(usos)} subetapa(s) do catálogo")
            print("   e será retirada dessas equipes. As subetapas já lançadas nas obras não são alteradas.")
        if not confirmar(f"\nRemover a profissão '{nome}'?"):
            return False
        for sub in usos:
            del sub["equipe_basica"][nome]
        if usos:
            salvar_etapas(etapas)
        return True

    gerenciar_lista_ordenada(
        lista,
        titulo=f"Profissões da disciplina '{disciplina}'",
        editar=editar,
        remover=remover,
        ao_alterar=lambda: salvar_profissoes(profissoes_dict),
    )


def gerenciar_profissoes():
    """Menu de cadastro de profissões filtradas por disciplina."""
    while True:
        limpar_terminal()
        disciplinas = carregar_disciplinas()
        if not disciplinas:
            print("❌ Nenhuma disciplina cadastrada no sistema.")
            input("\nPressione Enter para continuar...")
            break

        disc_sel, _ = selecionar_item_lista(
            disciplinas, titulo="Selecione a Disciplina"
        )
        if not disc_sel:
            break

        # Sub-loop de gerenciamento das profissões da disciplina escolhida
        while True:
            limpar_terminal()
            profissoes_dict = carregar_profissoes()
            lista_prof = profissoes_dict.get(disc_sel, [])

            print(f"=== PROFISSÕES DA DISCIPLINA: {disc_sel.upper()} ===\n")
            if not lista_prof:
                print("  └── (Nenhuma profissão cadastrada nesta disciplina)")
            else:
                for idx, prof in enumerate(lista_prof, 1):
                    print(f"  {idx}. {prof}")

            print("\n" + "-" * 40)
            print("1. Adicionar Profissão")
            print("2. Editar / Remover / Reordenar Profissões")
            print("0. Selecionar Outra Disciplina\n")

            op = input("Escolha uma opção: ").strip()

            if op == "1":
                nova_prof = (
                    input(f"\nNome da profissão para {disc_sel}: ")
                    .strip()
                    .title()
                )
                if nova_prof:
                    if disc_sel not in profissoes_dict:
                        profissoes_dict[disc_sel] = []

                    if nova_prof not in profissoes_dict[disc_sel]:
                        profissoes_dict[disc_sel].append(nova_prof)
                        salvar_profissoes(profissoes_dict)
                        print(
                            f"\n✓ Profissão '{nova_prof}' adicionada a '{disc_sel}'!"
                        )
                    else:
                        print(
                            f"\n⚠️ A profissão '{nova_prof}' já existe nesta disciplina."
                        )
                input("\nPressione Enter para continuar...")

            elif op == "2":
                editar_remover_reordenar_profissoes(disc_sel, profissoes_dict)

            elif op == "0":
                break