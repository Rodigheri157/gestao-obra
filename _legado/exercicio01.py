#to-do list

# O módulo 'json' é nativo do Python. Ele serve para converter dados entre
# estruturas do Python (dicionários e listas) e o formato de texto JSON.
import json
# O módulo 'os' (Operating System) permite interagir com o sistema operacional.
# Usamos aqui para verificar se um arquivo já existe na pasta antes de tentar abri-lo.
import os

# Definimos o nome do arquivo em uma variável constante (em maiúsculas por convenção).
# Se no futuro quisermos mudar o nome do arquivo, mudamos apenas nesta linha.
ARQ_DADOS = "tarefa json"

def limpar_terminal():
    """Limpa a tela do terminal identificando se é Windows ('nt') ou Linux/Mac."""
    # os.name retorna 'nt' se for Windows, ou 'posix' se for Linux/Mac
    os.system("cls" if os.name == "nt" else "clear")

def carregar_tarefas(): #Lê o arquivo json do disco, se nao existir cria um e retorna uma lista vazia

    # Se o arquivo 'tarefas.json' ainda não existir no computador (ex: primeira vez que roda),
    # não tentamos abri-lo, pois isso daria um erro FileNotFoundError.
    # Em vez disso, retornamos uma lista vazia [] para o programa começar do zero.
    if not os.path.exists(ARQ_DADOS):
        return[]

    # 'with open' é a forma mais segura de abrir arquivos em Python.
    # Ele garante que o arquivo será fechado automaticamente ao terminar o bloco,
    # mesmo que aconteça algum erro, evitando vazamento de memória ou corrupção de dados.
    # 'r' = modo de LEITURA (read).
    # encoding='utf-8' = garante suporte correto a acentos e caracteres em português (ã, ç, é).
    with open(ARQ_DADOS, "r", encoding="utf-8") as arquivo:

        # 'json.load(arquivo)' faz o trabalho pesado: lê o texto JSON do arquivo
        # e o converte automaticamente em uma lista de dicionários do Python.
        return json.load(arquivo)

def salvar_tarefa(tarefas): #Função responsável por GRAVAR a lista atualizada de tarefas de volta no arquivo.
    with open(ARQ_DADOS, "w", encoding="utf-8") as arquivo:
        # 'json.dump' pega a nossa lista do Python e escreve no formato JSON no arquivo.
        #
        # Parâmetros importantes:
        # 1. tarefas: a lista/dicionário Python que queremos salvar.
        # 2. arquivo: o ponteiro do arquivo aberto onde os dados serão salvos.
        # 3. indent=4: formata o JSON com recuos de 4 espaços, deixando o arquivo bonito
        #    e legível para humanos (caso você abra o tarefas.json no VS Code/Bloco de Notas).
        # 4. ensure_ascii=False: permite que acentos e caracteres especiais fiquem gravados
        #    como texto normal em vez de códigos unicodes esquisitos (ex: "Ação" em vez de "A\u00e7\u00e3o").
        json.dump(tarefas, arquivo, indent=4, ensure_ascii=False)

def listar_tarefas(tarefas): #Exibe no terminal todas as tarefas cadastradas
    print("\n--- SUAS TAREFAS ---")

    # Se a lista estiver vazia (len == 0), avisamos o usuário e saímos da função com 'return'
    if not tarefas:
        print("Nenhuma tarefa salva")
        return

    # 'enumerate(tarefas, 1)' percorre a lista e nos dá o índice junto com o elemento.
    # O '1' indica para a contagem começar em 1 (focado no usuário) e não em 0.
    for i, t in enumerate(tarefas, 1):
        
        # Operador Ternário em Python: forma rápida de definir um valor condicional.
        # Se t['concluida'] for True, usa '✓', senão usa um espaço em branco ' '.
        status = "✓" if t["concluida"] else ""

        # Acessamos os campos dentro do dicionário da tarefa usando as chaves ['titulo'] e ['categoria']
        print(f"{i}. [{status}] {t['titulo']} (Categoria: {t['categoria']})")

    

def adicionar_tarefa(tarefas):
    titulo = input("Descrição da tarefa: ")
    categoria = input("Categoria (ex: Estudo, Trabalho, Casa): ")

    # Montamos a estrutura de um "Documento" (dicionário Python).
    # É essa flexibilidade que imita o comportamento de bancos documentais.
    nova_tarefa = {
        "id": len(tarefas) + 1,  # Gera um ID numérico simples baseado no tamanho da lista
        "titulo": titulo,
        "categoria": categoria,
        "concluida": False,      # Toda tarefa criada começa como não concluída
    }

    # Adiciona o dicionário da nova tarefa no final da lista mantida na memória RAM
    tarefas.append(nova_tarefa)

    # IMPORTANTE: Salva a lista completa e atualizada no disco rígido (arquivo JSON)
    # garantindo que o dado persistirá mesmo se a aplicação for fechada logo em seguida.
    salvar_tarefa(tarefas)
    
    print("✓ Tarefa adicionada e salva no JSON!")

def main():     #função principal
    tarefas = carregar_tarefas()

    # 'while True' cria um loop infinito para manter o menu ativo
    # até que o usuário decida explicitamente sair (opção 3).
    while True:

        limpar_terminal()

        print("\n=== MENU ===")
        print("1. Listar tarefas")
        print("2. Adicionar tarefa")
        print("3. Sair")

        opcao = input("Escolha uma opção: ")

        if opcao == "1":
            limpar_terminal()
            listar_tarefas(tarefas)
            input("\nPressione Enter para voltar ao menu...") #Quando exibimos o resultado de uma listagem ou adição, precisamos fazer uma pausa antes de reiniciar o loop. Caso contrário, a tela seria limpa imediatamente e o usuário não conseguiria ler o que foi exibido
        elif opcao == "2":
            limpar_terminal()
            adicionar_tarefa(tarefas)
            input("\nPressione Enter para voltar ao menu...")
        elif opcao == "3":
            limpar_terminal()
            print("Até logo")
            break   
        else:
            print("opção errada, digite novamente")

if __name__ == "__main__":
    main()