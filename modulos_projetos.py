import os
from modulos_calendario import (
    CALENDARIO_PADRAO,
    converter_data,
    descrever_calendario,
    menu_calendario,
    obter_calendario,
)
from modulos_geral import (
    pasta_do_app,
    carregar_json,
    confirmar,
    editar_chave_dicionario,
    gerenciar_lista_ordenada,
    ler_float,
    limpar_terminal,
    remover_chave_dicionario,
    salvar_json,
    selecionar_item_lista,
)

DIRETORIO_ATUAL = pasta_do_app()
ARQUIVO_PROJETOS = os.path.join(DIRETORIO_ATUAL, "projetos.json")


def carregar_projetos():
    """Retorna a lista de projetos macros."""
    dados = carregar_json(ARQUIVO_PROJETOS, valor_padrao=[])
    return dados if isinstance(dados, list) else []


def salvar_projetos(projetos):
    """Salva a lista de projetos no JSON."""
    return salvar_json(ARQUIVO_PROJETOS, projetos)


def buscar_projeto(nome):
    """Retorna o projeto com o nome informado, ou None."""
    for p in carregar_projetos():
        if p.get("nome") == nome:
            return p
    return None


VALOR_HH_PADRAO = 1.0  # sem valor definido, 1 R$/HH mantém o custo proporcional ao HH (ponderação correta)


def obter_valor_hh(projeto_obj):
    """Valor do HH (R$/HH) do projeto; usa o padrão se não estiver definido."""
    try:
        valor = float((projeto_obj or {}).get("valor_hh") or 0)
    except (TypeError, ValueError):
        valor = 0
    return valor if valor > 0 else VALOR_HH_PADRAO


def descrever_valor_hh(projeto_obj):
    if (projeto_obj or {}).get("valor_hh"):
        return f"Valor do HH: R$ {obter_valor_hh(projeto_obj):,.2f}/HH"
    return f"Valor do HH: não definido (usando R$ {VALOR_HH_PADRAO:,.2f}/HH)"


def ler_data_inicio(mensagem):
    """Lê uma data válida (AAAA-MM-DD ou DD/MM/AAAA) e retorna em AAAA-MM-DD, ou '' se vazia."""
    while True:
        texto = input(mensagem).strip()
        if not texto:
            return ""
        data = converter_data(texto)
        if data:
            return data.isoformat()
        print("⚠️ Data inválida. Use DD/MM/AAAA ou AAAA-MM-DD.")


def cadastrar_projeto():
    """Cadastra um novo projeto macro com suas áreas funcionais."""
    limpar_terminal()
    print("--- CADASTRAR NOVO PROJETO MACRO ---\n")

    nome = input("Nome do Projeto (ex: Projeto XPTO - Complexo Industrial): ").strip().title()
    if not nome:
        print("\n❌ Nome inválido!")
        input("\nPressione Enter para continuar...")
        return

    cliente = input("Nome do Cliente / Empreendedor: ").strip().title()
    data_inicio = ler_data_inicio("Data de Início Prevista (DD/MM/AAAA): ")

    projetos = carregar_projetos()
    novo_proj = {
        "id": f"PRJ-{len(projetos) + 1:03d}",
        "nome": nome,
        "cliente": cliente,
        "data_inicio": data_inicio,
        "calendario": dict(CALENDARIO_PADRAO, feriados=[]),
        "areas": {}  # {"Área de Recebimento": ["Silo 01", "Tombador"]}
    }

    # Cadastro inicial de Áreas
    print("\n--- CADASTRO DE ÁREAS DO PROJETO ---")
    while True:
        area_nome = input("Nome da Área/Zona (ex: Área de Recebimento) [Enter para concluir]: ").strip().title()
        if not area_nome:
            break
        if area_nome not in novo_proj["areas"]:
            novo_proj["areas"][area_nome] = []
            print(f"  ✓ Área '{area_nome}' vinculada ao projeto.")

    projetos.append(novo_proj)
    if salvar_projetos(projetos):
        print(f"\n✓ Projeto '{nome}' cadastrado com sucesso!")

    input("\nPressione Enter para continuar...")


def gerenciar_obras_area(projeto_obj, area_nome, salvar):
    """Editar, remover e reordenar as obras de uma área (propaga as mudanças para o obras.json)."""
    # Import local: modulos_obras já importa este módulo (evita importação circular)
    from modulos_obras import excluir_obra_cadastrada, renomear_obra_cadastrada, resumo_dados_obra

    projeto_nome = projeto_obj["nome"]
    obras_area = projeto_obj["areas"][area_nome]

    def editar(nome_atual):
        novo = input(f"\nNovo nome para '{nome_atual}' [Enter para cancelar]: ").strip().title()
        if not novo or novo == nome_atual:
            return None
        if novo in obras_area:
            input("\n⚠️ Já existe uma obra com esse nome nesta área. Pressione Enter...")
            return None
        renomear_obra_cadastrada(projeto_nome, area_nome, nome_atual, novo)
        return novo

    def remover(nome):
        n_subs = resumo_dados_obra(projeto_nome, area_nome, nome)
        if n_subs:
            print(f"\n⚠️ A obra '{nome}' tem {n_subs} subetapa(s) lançada(s), com quantitativos e medições.")
            print("   Esses dados e os vínculos de outras obras com elas serão apagados.")
        if not confirmar(f"\nRemover a obra '{nome}'?"):
            return False
        excluir_obra_cadastrada(projeto_nome, area_nome, nome)
        return True

    gerenciar_lista_ordenada(
        obras_area,
        titulo=f"Obras da área '{area_nome}' (ordem de execução)",
        editar=editar,
        remover=remover,
        ao_alterar=salvar,
    )


def gerenciar_areas(projeto_obj, salvar):
    """Editar, remover e reordenar as áreas do projeto (propaga as mudanças para o obras.json)."""
    # Import local: modulos_obras já importa este módulo (evita importação circular)
    from modulos_obras import excluir_area_cadastrada, renomear_area_cadastrada, resumo_dados_area

    projeto_nome = projeto_obj["nome"]
    areas = projeto_obj.setdefault("areas", {})
    nomes = list(areas.keys())  # a ordem desta lista define a ordem das áreas (ex.: EAP do MS Project)

    def editar(nome_atual):
        novo = input(f"\nNovo nome para a área '{nome_atual}' [Enter para cancelar]: ").strip().title()
        if not novo or not editar_chave_dicionario(areas, nome_atual, novo):
            if novo:
                input("\nPressione Enter...")
            return None
        renomear_area_cadastrada(projeto_nome, nome_atual, novo)
        return novo

    def remover(nome):
        n_obras_cad = len(areas.get(nome, []))
        n_obras, n_subs = resumo_dados_area(projeto_nome, nome)
        if n_obras_cad:
            print(f"\n⚠️ A área '{nome}' tem {n_obras_cad} obra(s)/estrutura(s) cadastrada(s).")
        if n_subs:
            print(f"   {n_obras} delas têm {n_subs} subetapa(s) lançada(s), com quantitativos e medições.")
            print("   Esses dados e os vínculos de outras obras com elas serão apagados.")
        if not remover_chave_dicionario(areas, nome, f"\nRemover a área '{nome}'?"):
            input("\nPressione Enter...")
            return False
        excluir_area_cadastrada(projeto_nome, nome)
        return True

    def ao_alterar():
        # Reconstrói o dicionário de áreas na ordem atual da lista e persiste
        reordenado = {n: areas[n] for n in nomes}
        areas.clear()
        areas.update(reordenado)
        salvar()

    gerenciar_lista_ordenada(
        nomes,
        titulo=f"Áreas do projeto '{projeto_nome}'",
        rotulo=lambda n: f"{n} ({len(areas.get(n, []))} obras/estruturas)",
        editar=editar,
        remover=remover,
        ao_alterar=ao_alterar,
    )


def gerenciar_areas_projeto(projeto_obj, todos_projetos, idx_proj):
    """Gerencia áreas e obras cadastradas no escopo do projeto."""
    while True:
        limpar_terminal()
        print(f"=== PROJETO: {projeto_obj['nome'].upper()} ===")
        print(f"Cliente: {projeto_obj.get('cliente', 'N/I')} | Código: {projeto_obj.get('id')}")
        data_ini = converter_data(projeto_obj.get("data_inicio", ""))
        print(f"Início: {data_ini.strftime('%d/%m/%Y') if data_ini else '(não definida)'}")
        print(f"{descrever_calendario(obter_calendario(projeto_obj))}")
        print(f"{descrever_valor_hh(projeto_obj)}\n")

        areas_dict = projeto_obj.get("areas", {})
        if not areas_dict:
            print("  └── (Nenhuma área cadastrada neste projeto)")
        else:
            for area, obras in areas_dict.items():
                tot_obras = len(obras)
                print(f"  • ÁREA: {area} ({tot_obras} obras/estruturas)")
                for ob in obras:
                    print(f"      └── Obra: {ob}")

        print("\n" + "-" * 50)
        print("1. Adicionar Nova Área ao Projeto")
        print("2. Adicionar Obra/Estrutura a uma Área")
        print("3. Alterar Data de Início do Projeto")
        print("4. Configurar Calendário de Trabalho")
        print("5. Editar / Remover / Reordenar Obras de uma Área")
        print("6. Editar / Remover / Reordenar Áreas do Projeto")
        print("7. Definir Valor do HH (R$/HH) — ponderação do cronograma")
        print("0. Voltar\n")

        op = input("Escolha uma opção: ").strip()

        if op == "1":
            nova_area = input("\nNome da Nova Área: ").strip().title()
            if nova_area:
                if nova_area not in projeto_obj["areas"]:
                    projeto_obj["areas"][nova_area] = []
                    todos_projetos[idx_proj] = projeto_obj
                    salvar_projetos(todos_projetos)
                    print(f"\n✓ Área '{nova_area}' adicionada!")
                else:
                    print("\n⚠️ Área já cadastrada.")
            input("\nPressione Enter para continuar...")

        elif op == "2":
            lista_areas = list(projeto_obj["areas"].keys())
            area_sel, _ = selecionar_item_lista(lista_areas, titulo="Selecione a Área")
            if area_sel:
                nova_obra = input(f"\nNome da Obra/Estrutura para '{area_sel}' (ex: Silo 01): ").strip().title()
                if nova_obra:
                    if nova_obra not in projeto_obj["areas"][area_sel]:
                        projeto_obj["areas"][area_sel].append(nova_obra)
                        todos_projetos[idx_proj] = projeto_obj
                        salvar_projetos(todos_projetos)
                        print(f"\n✓ Obra '{nova_obra}' adicionada à '{area_sel}'!")
                    else:
                        print("\n⚠️ Obra já existe nesta área.")
                input("\nPressione Enter para continuar...")

        elif op == "3":
            nova_data = ler_data_inicio("\nNova Data de Início (DD/MM/AAAA) [Enter para manter]: ")
            if nova_data:
                projeto_obj["data_inicio"] = nova_data
                todos_projetos[idx_proj] = projeto_obj
                salvar_projetos(todos_projetos)
                print("\n✓ Data de início atualizada!")
                input("\nPressione Enter para continuar...")

        elif op == "4":
            if menu_calendario(projeto_obj):
                todos_projetos[idx_proj] = projeto_obj
                salvar_projetos(todos_projetos)

        elif op == "5":
            lista_areas = list(projeto_obj["areas"].keys())
            area_sel, _ = selecionar_item_lista(lista_areas, titulo="Selecione a Área")
            if area_sel:
                def salvar():
                    todos_projetos[idx_proj] = projeto_obj
                    salvar_projetos(todos_projetos)
                gerenciar_obras_area(projeto_obj, area_sel, salvar)

        elif op == "6":
            def salvar():
                todos_projetos[idx_proj] = projeto_obj
                salvar_projetos(todos_projetos)
            gerenciar_areas(projeto_obj, salvar)

        elif op == "7":
            print("\nO valor do HH é usado para ponderar o cronograma por HH: no MS Project ele vira a")
            print("taxa padrão dos recursos (Custo = HH x valor), e no memorial gera a coluna Valor (R$).")
            atual = obter_valor_hh(projeto_obj)
            novo = ler_float(f"\nValor do HH em R$ [{atual:.2f}]: ", valor_padrao=atual)
            if novo > 0:
                projeto_obj["valor_hh"] = round(novo, 2)
                todos_projetos[idx_proj] = projeto_obj
                salvar_projetos(todos_projetos)
                print(f"\n✓ Valor do HH atualizado para R$ {novo:,.2f}/HH.")
            else:
                print("\n⚠️ Informe um valor maior que zero.")
            input("\nPressione Enter para continuar...")

        elif op == "0":
            break


def menu_projetos():
    """Menu principal de projetos macros."""
    while True:
        limpar_terminal()
        projetos = carregar_projetos()

        print("=== PROJETOS MACROS E ÁREAS ===\n")
        if not projetos:
            print("  └── (Nenhum projeto cadastrado)")
        else:
            for idx, p in enumerate(projetos, 1):
                tot_areas = len(p.get("areas", {}))
                print(f"  {idx}. {p['nome']} (Cliente: {p.get('cliente')}) - {tot_areas} áreas")

        print("\n" + "-" * 50)
        print("1. Cadastrar Novo Projeto")
        print("2. Gerenciar Áreas e Obras de um Projeto")
        print("0. Voltar ao Menu Principal\n")

        op = input("Escolha uma opção: ").strip()

        if op == "1":
            cadastrar_projeto()
        elif op == "2":
            proj_sel, idx_sel = selecionar_item_lista(projetos, titulo="Selecione o Projeto", chave_nome="nome")
            if proj_sel:
                gerenciar_areas_projeto(proj_sel, projetos, idx_sel)
        elif op == "0":
            break