from modulos_disc import gerenciar_disciplinas
from modulos_etapas import menu_etapas
from modulos_geral import limpar_terminal
from modulos_obras import menu_obras
from modulos_profissoes import gerenciar_profissoes
from modulos_projetos import menu_projetos
from modulos_relatorios import menu_relatorios  # Import do novo módulo


def menu_parametros():
    """Menu de cadastros de parâmetros globais de referência."""
    while True:
        limpar_terminal()
        print("=== PARÂMETROS E CADASTROS GLOBAIS ===\n")
        print("1. Cadastrar Disciplinas")
        print("2. Cadastrar Profissões (por Disciplina)")
        print("3. Catálogo Geral de Etapas e Subetapas (Índices Padrão)")
        print("0. Voltar ao Menu Principal\n")

        op = input("Escolha uma opção: ").strip()

        if op == "1":
            gerenciar_disciplinas()
        elif op == "2":
            gerenciar_profissoes()
        elif op == "3":
            menu_etapas()
        elif op == "0":
            break


def main():
    """Ponto de entrada do sistema EAP Engenharia."""
    while True:
        limpar_terminal()
        print("==================================================")
        print("    SISTEMA DE GESTÃO DE EAP E PROJETOS - PYTHON   ")
        print("==================================================\n")
        print("1. Parâmetros e Catálogos Globais")
        print("2. Cadastro Macro de Projetos e Áreas")
        print("3. Gestão de Obras (EAP Executivo e Quantitativos)")
        print("4. Emissão de Relatórios (Memorial, Cronograma e Histograma)")
        print("0. Sair\n")

        opcao = input("Escolha uma opção: ").strip()

        if opcao == "1":
            menu_parametros()
        elif opcao == "2":
            menu_projetos()
        elif opcao == "3":
            menu_obras()
        elif opcao == "4":
            menu_relatorios()
        elif opcao == "0":
            limpar_terminal()
            print("Encerrando o sistema...")
            break


if __name__ == "__main__":
    main()