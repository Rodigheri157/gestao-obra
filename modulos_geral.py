import json
import os
import sys


def pasta_do_app():
    """Pasta dos dados (JSON) e arquivos gerados: a do .exe quando empacotado, senão a dos .py."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def nome_subetapa(sub):
    """
    Nome de exibição de uma subetapa lançada na obra: 'Nome do catálogo - Complemento'.
    O complemento distingue lançamentos da mesma subetapa na mesma etapa
    (ex.: 'Execução De Estacas - Blocos balança' / 'Execução De Estacas - Rampas de acesso').
    """
    comp = (sub.get("complemento") or "").strip()
    return f"{sub['nome']} - {comp}" if comp else sub["nome"]


def limpar_terminal():
    """Limpa a tela do terminal."""
    os.system("cls" if os.name == "nt" else "clear")


# ==============================================================================
# PERSISTÊNCIA GENÉRICA DE ARQUIVOS JSON
# ==============================================================================

def carregar_json(caminho_arquivo, valor_padrao=None):
    """Lê um arquivo JSON genérico e retorna seu conteúdo com fallback seguro."""
    if valor_padrao is None:
        valor_padrao = []

    if not os.path.exists(caminho_arquivo):
        return valor_padrao

    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as arq:
            return json.load(arq)
    except Exception as e:
        print(f"⚠️ Erro ao ler o arquivo '{caminho_arquivo}': {e}")
        return valor_padrao


def salvar_json(caminho_arquivo, dados):
    """Escreve dados em um arquivo JSON genérico formatado."""
    try:
        with open(caminho_arquivo, "w", encoding="utf-8") as arq:
            json.dump(dados, arq, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar o arquivo '{caminho_arquivo}': {e}")
        return False


# ==============================================================================
# LEITURA E SELEÇÃO INTERATIVA
# ==============================================================================

def ler_float(mensagem, valor_padrao=0.0):
    """Lê um número decimal do usuário aceitando vírgula ou ponto."""
    entrada = input(mensagem).strip().replace(",", ".")
    if not entrada:
        return valor_padrao
    try:
        val = float(entrada)
        return val if val >= 0 else valor_padrao
    except ValueError:
        print("⚠️ Valor inválido! Assumindo valor padrão.")
        return valor_padrao


def ler_int(mensagem, valor_padrao=1):
    """Lê um número inteiro do usuário."""
    entrada = input(mensagem).strip()
    if not entrada:
        return valor_padrao
    try:
        val = int(entrada)
        return val if val > 0 else valor_padrao
    except ValueError:
        print("⚠️ Valor inválido! Assumindo valor padrão.")
        return valor_padrao


def ler_inteiro(mensagem, valor_padrao=0):
    """Lê um número inteiro do usuário aceitando zero e negativos (ex.: defasagens)."""
    entrada = input(mensagem).strip()
    if not entrada:
        return valor_padrao
    try:
        return int(entrada)
    except ValueError:
        print("⚠️ Valor inválido! Assumindo valor padrão.")
        return valor_padrao


def selecionar_item_lista(lista, titulo="SELEÇÃO", chave_nome=None):
    """Exibe uma lista numerada genérica e retorna a escolha do usuário ou None."""
    if not lista:
        print(f"\n❌ Nenhuma opção disponível para {titulo.lower()}.")
        input("\nPressione Enter para continuar...")
        return None, None

    print(f"--- {titulo.upper()} ---")
    for idx, item in enumerate(lista, 1):
        if chave_nome and isinstance(item, dict):
            print(f"  {idx}. {item.get(chave_nome, 'Sem nome')}")
        else:
            print(f"  {idx}. {item}")

    print("\n  0. Cancelar / Voltar\n")
    op = input("Escolha uma opção: ").strip()

    if op.isdigit():
        idx_sel = int(op) - 1
        if 0 <= idx_sel < len(lista):
            return lista[idx_sel], idx_sel

    return None, None

# ==============================================================================
# EDICÃO E REMOÇÃO EM DICIONÁRIOS REUTILIZÁVEIS
# ==============================================================================

def editar_chave_dicionario(dicionario, chave_antiga, novo_nome):
    """
    Renomeia uma chave dentro de um dicionário mantendo a ordem e seus valores associados.
    Retorna True se a alteração foi realizada com sucesso.
    """
    if chave_antiga not in dicionario:
        print(f"⚠️ A chave '{chave_antiga}' não existe.")
        return False
    
    if not novo_nome or novo_nome == chave_antiga:
        print("⚠️ Novo nome inválido ou idêntico ao atual.")
        return False

    if novo_nome in dicionario:
        print(f"⚠️ Já existe um item cadastrado com o nome '{novo_nome}'.")
        return False

    # Reconstrói o dicionário mantendo a mesma ordem das chaves
    novo_dict = {}
    for k, v in dicionario.items():
        if k == chave_antiga:
            novo_dict[novo_nome] = v
        else:
            novo_dict[k] = v

    dicionario.clear()
    dicionario.update(novo_dict)
    return True


def remover_chave_dicionario(dicionario, chave_para_remover, mensagem_confirmacao=None):
    """
    Remove uma chave de um dicionário genérico após validação e confirmação.
    Retorna True se o item foi removido.
    """
    if chave_para_remover not in dicionario:
        print(f"⚠️ O item '{chave_para_remover}' não foi encontrado.")
        return False

    if mensagem_confirmacao:
        confirma = input(f"{mensagem_confirmacao} (S/N): ").strip().upper()
        if confirma != "S":
            print("\nOperação cancelada.")
            return False

    del dicionario[chave_para_remover]
    return True

# ==============================================================================
# LISTAS ORDENADAS REUTILIZÁVEIS (editar, remover, subir e descer)
# ==============================================================================

def mover_item_lista(lista, idx, deslocamento):
    """
    Move o item da posição 'idx' em 'deslocamento' posições (-1 sobe, +1 desce).
    Retorna o novo índice, ou None se o movimento sair dos limites da lista.
    """
    novo_idx = idx + deslocamento
    if not (0 <= idx < len(lista)) or not (0 <= novo_idx < len(lista)):
        return None
    lista.insert(novo_idx, lista.pop(idx))
    return novo_idx


def confirmar(mensagem):
    """Pergunta S/N ao usuário e retorna True se confirmou."""
    return input(f"{mensagem} (S/N): ").strip().upper() == "S"


def gerenciar_lista_ordenada(lista, titulo, rotulo=str, editar=None, remover=None, ao_alterar=None,
                             permite_remover=True):
    """
    Menu genérico para manter uma lista em que a ORDEM importa (obras de uma área,
    subetapas de uma etapa / sequência executiva etc.). Altera 'lista' no próprio lugar.

    Parâmetros (todos opcionais, exceto lista e titulo):
      rotulo(item)         -> texto exibido para o item.
      editar(item)         -> retorna o item alterado (pode ser um novo objeto/str) ou None se cancelado.
                              Sem 'editar', a opção de edição não aparece.
      remover(item)        -> faz a confirmação e os efeitos colaterais (ex.: apagar dados ligados)
                              e retorna True para remover. Sem 'remover', usa uma confirmação simples.
      ao_alterar()         -> chamado após cada alteração (normalmente para salvar no JSON).
      permite_remover      -> False esconde a opção Remover (menu só de reordenação).

    Retorna True se a lista foi alterada.
    """
    alterou = False
    selecionado = None  # índice destacado (segue o item ao subir/descer)

    def registrar():
        nonlocal alterou
        alterou = True
        if ao_alterar:
            ao_alterar()

    while True:
        limpar_terminal()
        print(f"=== {titulo.upper()} ===\n")
        if not lista:
            print("  └── (Lista vazia)")
        for i, item in enumerate(lista, 1):
            marca = "►" if selecionado == i - 1 else " "
            print(f" {marca}{i:>3}. {rotulo(item)}")

        print("\n" + "-" * 50)
        opcoes = []
        if editar:
            opcoes.append(("E", "Editar"))
        if permite_remover:
            opcoes.append(("R", "Remover"))
        opcoes += [("S", "Subir"), ("D", "Descer"), ("M", "Mover p/ posição"), ("0", "Voltar")]
        print(" | ".join(f"{k}. {txt}" for k, txt in opcoes))
        print("(atalho: digite a letra seguida do nº, ex.: S3 = subir o item 3 | M5 = mover o item 5)\n")

        entrada = input("Escolha uma opção: ").strip().upper()
        if entrada == "0" or not entrada:
            return alterou

        acao, num = entrada[0], entrada[1:].strip()
        if acao not in {k for k, _ in opcoes}:
            continue
        if not lista:
            input("\n⚠️ Lista vazia. Pressione Enter...")
            continue

        # Item alvo: número digitado junto, o item destacado (subir/descer em sequência) ou pergunta
        if not num and acao in "SD" and selecionado is not None:
            idx = selecionado
        else:
            if not num:
                num = input("Nº do item: ").strip()
            if not num.isdigit() or not (1 <= int(num) <= len(lista)):
                input("\n⚠️ Número inválido. Pressione Enter...")
                continue
            idx = int(num) - 1

        item = lista[idx]
        if acao == "E":
            novo = editar(item)
            if novo is not None:
                lista[idx] = novo
                selecionado = idx
                registrar()
        elif acao == "R":
            ok = remover(item) if remover else confirmar(f"\n⚠️ Remover '{rotulo(item)}'?")
            if ok:
                lista.pop(idx)
                selecionado = None
                registrar()
        elif acao in "SD":
            novo_idx = mover_item_lista(lista, idx, -1 if acao == "S" else 1)
            if novo_idx is None:
                selecionado = idx
                input("\n⚠️ O item já está no limite da lista. Pressione Enter...")
            else:
                selecionado = novo_idx
                registrar()
        elif acao == "M":
            pos = input(f"Nova posição para '{rotulo(item)}' (1 a {len(lista)}): ").strip()
            if not pos.isdigit() or not (1 <= int(pos) <= len(lista)):
                input("\n⚠️ Posição inválida. Pressione Enter...")
                continue
            novo_idx = int(pos) - 1
            if novo_idx != idx:
                lista.insert(novo_idx, lista.pop(idx))
                registrar()
            selecionado = novo_idx


# ==============================================================================
# RENOMEAÇÃO EM CASCATA (catálogos -> cadastros que usam o nome)
# ==============================================================================

def _juntar_valores(a, b):
    """Junta dois valores de mesma chave: listas concatenam, dicionários mesclam, números somam."""
    if isinstance(a, list):
        return a + b
    if isinstance(a, dict):
        r = dict(a)
        for k, v in b.items():
            r[k] = _juntar_valores(r[k], v) if k in r else v
        return r
    return a + b


def renomear_chave_mesclando(dicionario, chave_antiga, chave_nova):
    """
    Renomeia uma chave mantendo a ordem. Se 'chave_nova' já existir, os conteúdos são
    juntados (ex.: duas etapas com o mesmo nome numa obra, ou o mesmo profissional numa equipe).
    """
    if chave_antiga not in dicionario or chave_antiga == chave_nova:
        return
    valor_antigo = dicionario[chave_antiga]
    ja_existe = chave_nova in dicionario
    itens = list(dicionario.items())
    dicionario.clear()
    for k, v in itens:
        if k == chave_antiga:
            if not ja_existe:
                dicionario[chave_nova] = v
        elif k == chave_nova:
            dicionario[chave_nova] = _juntar_valores(v, valor_antigo)
        else:
            dicionario[k] = v


def propagar_para_obras(funcao, args, descricao):
    """
    Pergunta se uma renomeação feita no catálogo deve valer também para as subetapas já
    lançadas nas obras. 'funcao(*args, aplicar=False)' deve retornar quantas subetapas usam
    o nome antigo; com aplicar=True, faz a renomeação. Retorna True se exibiu mensagem.
    """
    n = funcao(*args, aplicar=False)
    if not n:
        return False
    print(f"\nℹ️ {n} subetapa(s) já lançada(s) nas obras usam {descricao}.")
    if confirmar("   Aplicar a nova nomenclatura também nas obras?"):
        funcao(*args, aplicar=True)
        print("✓ Obras atualizadas.")
    else:
        print("   Obras mantidas com o nome antigo.")
    return True
