import os
from modulos_geral import (
    pasta_do_app,
    carregar_json,
    confirmar,
    gerenciar_lista_ordenada,
    limpar_terminal,
    propagar_para_obras,
    renomear_chave_mesclando,
    salvar_json,
)

DIRETORIO_ATUAL = pasta_do_app()
ARQUIVO_DISCIPLINAS = os.path.join(DIRETORIO_ATUAL, "disciplinas.json")


def carregar_disciplinas():
    """Retorna a lista de disciplinas cadastradas no JSON."""
    padrao_inicial = ["Civil", "Mecânica", "Elétrica", "Automação", "Tubulação"]
    if not os.path.exists(ARQUIVO_DISCIPLINAS):
        salvar_json(ARQUIVO_DISCIPLINAS, padrao_inicial)
        return padrao_inicial

    dados = carregar_json(ARQUIVO_DISCIPLINAS, valor_padrao=padrao_inicial)
    return dados if isinstance(dados, list) else []


def salvar_disciplinas(disciplinas):
    """Salva a lista de disciplinas no JSON."""
    return salvar_json(ARQUIVO_DISCIPLINAS, disciplinas)


def editar_remover_reordenar_disciplinas(disciplinas):
    """Editar, remover e reordenar disciplinas (propaga para etapas, profissões e, se confirmado, obras)."""
    # Imports locais: esses módulos já importam este (evita importação circular)
    from modulos_etapas import carregar_etapas, salvar_etapas
    from modulos_obras import renomear_disciplina_nas_obras
    from modulos_profissoes import carregar_profissoes, salvar_profissoes

    def editar(nome_atual):
        novo = input(f"\nNovo nome para a disciplina '{nome_atual}' [Enter para cancelar]: ").strip().title()
        if not novo or novo == nome_atual:
            return None
        if novo in disciplinas:
            input("\n⚠️ Já existe uma disciplina com esse nome. Pressione Enter...")
            return None

        # Catálogo de etapas e profissões acompanham a renomeação
        etapas = carregar_etapas()
        if any(et.get("disciplina") == nome_atual for et in etapas):
            for et in etapas:
                if et.get("disciplina") == nome_atual:
                    et["disciplina"] = novo
            salvar_etapas(etapas)
        profissoes = carregar_profissoes()
        if nome_atual in profissoes:
            renomear_chave_mesclando(profissoes, nome_atual, novo)
            salvar_profissoes(profissoes)

        if propagar_para_obras(renomear_disciplina_nas_obras, (nome_atual, novo), f"a disciplina '{nome_atual}'"):
            input("\nPressione Enter para continuar...")
        return novo

    def remover(nome):
        etapas = carregar_etapas()
        n_etapas = sum(1 for et in etapas if et.get("disciplina") == nome)
        profissoes = carregar_profissoes()
        n_prof = len(profissoes.get(nome, []))
        if n_etapas or n_prof:
            print(f"\n⚠️ A disciplina '{nome}' tem {n_etapas} etapa(s) no catálogo e {n_prof} profissão(ões) cadastrada(s).")
            print("   Elas também serão removidas. As subetapas já lançadas nas obras não são alteradas.")
        if not confirmar(f"\nRemover a disciplina '{nome}'?"):
            return False
        if n_etapas:
            salvar_etapas([et for et in etapas if et.get("disciplina") != nome])
        if nome in profissoes:
            del profissoes[nome]
            salvar_profissoes(profissoes)
        return True

    gerenciar_lista_ordenada(
        disciplinas,
        titulo="Disciplinas",
        editar=editar,
        remover=remover,
        ao_alterar=lambda: salvar_disciplinas(disciplinas),
    )


def gerenciar_disciplinas():
    """Menu para cadastrar, editar, remover e reordenar disciplinas."""
    while True:
        limpar_terminal()
        disciplinas = carregar_disciplinas()

        print("=== CADASTRO DE DISCIPLINAS ===\n")
        if not disciplinas:
            print("  └── (Nenhuma disciplina cadastrada)")
        else:
            for idx, disc in enumerate(disciplinas, 1):
                print(f"  {idx}. {disc}")

        print("\n" + "-" * 40)
        print("1. Adicionar Disciplina")
        print("2. Editar / Remover / Reordenar Disciplinas")
        print("0. Voltar ao Menu Anterior\n")

        op = input("Escolha uma opção: ").strip()

        if op == "1":
            nova = input("\nNome da nova disciplina: ").strip().title()
            if nova and nova not in disciplinas:
                disciplinas.append(nova)
                salvar_disciplinas(disciplinas)
                print(f"\n✓ Disciplina '{nova}' cadastrada com sucesso!")
            elif nova in disciplinas:
                print("\n⚠️ Disciplina já existente.")
            input("\nPressione Enter para continuar...")

        elif op == "2":
            editar_remover_reordenar_disciplinas(disciplinas)

        elif op == "0":
            break
