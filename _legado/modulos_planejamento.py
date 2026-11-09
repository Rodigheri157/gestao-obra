import csv
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Importações dos módulos base do sistema
from modulo_obras import ARQUIVO_OBRAS, carregar_obras, salvar_obras
from modulos_geral import limpar_terminal


# ==============================================================================
# 1. FUNÇÕES AUXILIARES DE CÁLCULO
# ==============================================================================

def calcular_dias_subetapa(quantidade, produtividade_dia):
    """Calcula a duração necessária em dias úteis com base na quantidade e produtividade."""
    if produtividade_dia <= 0 or quantidade <= 0:
        return 1
    dias = quantidade / produtividade_dia
    return int(dias) + (1 if dias % 1 != 0 else 0)


# ==============================================================================
# 2. SELEÇÃO E NAVEGAÇÃO DE OBRAS
# ==============================================================================

def selecionar_obra():
    """Exibe as obras cadastradas no sistema e retorna a obra escolhida."""
    limpar_terminal()
    print("--- SELEÇÃO DE OBRA PARA PLANEJAMENTO ---\n")

    obras = carregar_obras()
    if not obras:
        print("❌ Nenhuma obra cadastrada no sistema.")
        input("\nPressione Enter para continuar...")
        return None

    print("Obras disponíveis:")
    for idx, obra in enumerate(obras, 1):
        nome_obra = (
            obra.get("nome", "Sem Nome") if isinstance(obra, dict) else str(obra)
        )
        print(f"  {idx}. {nome_obra}")

    print("\n  0. Voltar")

    n = input("\nDigite o número da obra que deseja planejar: ").strip()

    if n == "0":
        return None

    if n.isdigit() and 1 <= int(n) <= len(obras):
        return obras[int(n) - 1]
    else:
        print("\n❌ Número de obra inválido.")
        input("\nPressione Enter para continuar...")
        return None


# ==============================================================================
# 3. CADASTRO DE PARÂMETROS DE ENGENHARIA NAS SUBETAPAS
# ==============================================================================

def cadastrar_parametros_subetapas(obra_atual):
    """Cadastra Unidade, Quantidade Física e Produtividade Diária por Subetapa."""
    limpar_terminal()
    print(
        f"--- CADASTRAR PARÂMETROS DE ENGENHARIA: {obra_atual['nome'].upper()} ---\n"
    )

    disciplinas = obra_atual.get("disciplinas", {})
    if not disciplinas:
        print("❌ Nenhuma disciplina/etapa cadastrada nesta obra.")
        input("\nPressione Enter para continuar...")
        return

    # 1. SELEÇÃO DA DISCIPLINA
    lista_disc = list(disciplinas.keys())
    print("Disciplinas da obra:")
    for idx, d in enumerate(lista_disc, 1):
        print(f"  {idx}. {d}")

    op_d = input("\nEscolha o número da disciplina: ").strip()
    if not (op_d.isdigit() and 1 <= int(op_d) <= len(lista_disc)):
        print("\n❌ Opção inválida.")
        input("\nPressione Enter para continuar...")
        return

    disc_sel = lista_disc[int(op_d) - 1]
    etapas_dict = disciplinas[disc_sel]

    if not etapas_dict or not isinstance(etapas_dict, dict):
        print(f"\n❌ A disciplina '{disc_sel}' não possui etapas cadastradas.")
        input("\nPressione Enter para continuar...")
        return

    # 2. SELEÇÃO DA ETAPA
    limpar_terminal()
    lista_etapas = list(etapas_dict.keys())
    print(f"Etapas em '{disc_sel}':")
    for idx, e in enumerate(lista_etapas, 1):
        print(f"  {idx}. {e}")

    op_e = input("\nEscolha o número da etapa: ").strip()
    if not (op_e.isdigit() and 1 <= int(op_e) <= len(lista_etapas)):
        print("\n❌ Opção inválida.")
        input("\nPressione Enter para continuar...")
        return

    etapa_sel = lista_etapas[int(op_e) - 1]
    subetapas = etapas_dict[etapa_sel]

    if not subetapas or not isinstance(subetapas, list):
        print(f"\n❌ A etapa '{etapa_sel}' não possui subetapas cadastradas.")
        input("\nPressione Enter para continuar...")
        return

    # 3. SELEÇÃO DA SUBETAPA
    limpar_terminal()
    print(
        f"Subetapas em '{etapa_sel}' ({disc_sel} | Obra: {obra_atual['nome']}):\n"
    )

    for idx, sub in enumerate(subetapas, 1):
        if isinstance(sub, dict):
            nome_sub = sub.get("nome", "Sem Nome")
            und = sub.get("unidade", "un")
            qtd = sub.get("quantidade", 0.0)
            prod = sub.get("produtividade_equipe_dia", 0.0)
            print(
                f"  {idx}. {nome_sub} -> Quantidade: {qtd} {und} | Produtividade: {prod} {und}/dia"
            )
        else:
            print(f"  {idx}. {sub} -> (Sem parâmetros cadastrados)")

    op_sub = input("\nEscolha a subetapa para parametrizar: ").strip()
    if not (op_sub.isdigit() and 1 <= int(op_sub) <= len(subetapas)):
        print("\n❌ Opção inválida.")
        input("\nPressione Enter para continuar...")
        return

    idx_sub = int(op_sub) - 1
    sub_obj = subetapas[idx_sub]

    # Converte string simples em estrutura de dicionário
    if isinstance(sub_obj, str):
        sub_obj = {
            "nome": sub_obj,
            "unidade": "m³",
            "quantidade": 0.0,
            "produtividade_equipe_dia": 1.0,
        }

    # 4. ENTRADA DOS DADOS DE ENGENHARIA
    limpar_terminal()
    print(f"=== EDITANDO SUBETAPA: {sub_obj['nome'].upper()} ===\n")
    print(f"Unidade Atual     : {sub_obj.get('unidade', 'un')}")
    print(f"Quantidade Atual  : {sub_obj.get('quantidade', 0.0)}")
    print(f"Produtividade/Dia : {sub_obj.get('produtividade_equipe_dia', 0.0)}")
    print("\n" + "-" * 50 + "\n")

    nova_unidade = input(
        f"Nova Unidade (ex: m³, m², kg, un) [{sub_obj.get('unidade', 'un')}]: "
    ).strip()
    if nova_unidade:
        sub_obj["unidade"] = nova_unidade

    nova_qtd = input(
        f"Nova Quantidade Física Total [{sub_obj.get('quantidade', 0.0)}]: "
    ).strip()
    if nova_qtd:
        try:
            sub_obj["quantidade"] = float(nova_qtd.replace(",", "."))
        except ValueError:
            print("\n⚠️ Quantidade inválida! Mantendo o valor original.")

    nova_prod = input(
        f"Nova Produtividade Diária da Equipe [{sub_obj.get('produtividade_equipe_dia', 1.0)}]: "
    ).strip()
    if nova_prod:
        try:
            sub_obj["produtividade_equipe_dia"] = float(
                nova_prod.replace(",", ".")
            )
        except ValueError:
            print("\n⚠️ Produtividade inválida! Mantendo o valor original.")

    # Atualiza a subetapa na obra local
    subetapas[idx_sub] = sub_obj

    # Persiste a alteração no catálogo de obras e sincroniza com os projetos
    obras = carregar_obras()
    for idx, ob in enumerate(obras):
        if ob.get("nome") == obra_atual.get("nome"):
            obras[idx] = obra_atual
            break

    if salvar_obras(obras):
        print(
            f"\n✓ Parâmetros da subetapa '{sub_obj['nome']}' salvos e sincronizados!"
        )

    input("\nPressione Enter para continuar...")


# ==============================================================================
# 4. EXPORTADOR DO CRONOGRAMA PARA MS PROJECT (.XML)
# ==============================================================================

def exportar_cronograma_ms_project(obra):
    """Gera o arquivo XML da EAP estruturada para importação direta no MS Project."""
    caminho_saida = f"Cronograma_{obra['nome'].replace(' ', '_')}.xml"

    project = ET.Element("Project", xmlns="http://schemas.microsoft.com/project")

    ET.SubElement(project, "Name").text = obra.get("nome", "Obra EAP")
    ET.SubElement(project, "Title").text = (
        f"Cronograma EAP - {obra.get('nome')}"
    )

    start_date = datetime.now()
    ET.SubElement(project, "StartDate").text = start_date.strftime(
        "%Y-%m-%dT08:00:00"
    )

    tasks = ET.SubElement(project, "Tasks")
    task_id = 1
    data_cursor = start_date
    disciplinas = obra.get("disciplinas", {})

    # Nível 1: Obra (Resumo)
    t_root = ET.SubElement(tasks, "Task")
    ET.SubElement(t_root, "UID").text = str(task_id)
    ET.SubElement(t_root, "ID").text = str(task_id)
    ET.SubElement(t_root, "Name").text = obra.get("nome").upper()
    ET.SubElement(t_root, "OutlineLevel").text = "1"
    ET.SubElement(t_root, "Summary").text = "1"
    task_id += 1

    # Nível 2: Disciplinas
    for disc, etapas in disciplinas.items():
        t_disc = ET.SubElement(tasks, "Task")
        ET.SubElement(t_disc, "UID").text = str(task_id)
        ET.SubElement(t_disc, "ID").text = str(task_id)
        ET.SubElement(t_disc, "Name").text = disc
        ET.SubElement(t_disc, "OutlineLevel").text = "2"
        ET.SubElement(t_disc, "Summary").text = "1"
        task_id += 1

        # Nível 3: Etapas
        for etapa, subetapas in etapas.items():
            t_etapa = ET.SubElement(tasks, "Task")
            ET.SubElement(t_etapa, "UID").text = str(task_id)
            ET.SubElement(t_etapa, "ID").text = str(task_id)
            ET.SubElement(t_etapa, "Name").text = etapa
            ET.SubElement(t_etapa, "OutlineLevel").text = "3"
            ET.SubElement(t_etapa, "Summary").text = "1"
            task_id += 1

            # Nível 4: Subetapas
            for sub in subetapas:
                t_sub = ET.SubElement(tasks, "Task")
                ET.SubElement(t_sub, "UID").text = str(task_id)
                ET.SubElement(t_sub, "ID").text = str(task_id)

                if isinstance(sub, dict):
                    nome_sub = sub.get("nome", "Subetapa")
                    qtd = sub.get("quantidade", 0)
                    prod = sub.get("produtividade_equipe_dia", 1)
                    dias = calcular_dias_subetapa(qtd, prod)
                else:
                    nome_sub = str(sub)
                    dias = 1

                data_fim = data_cursor + timedelta(days=dias)

                ET.SubElement(t_sub, "Name").text = nome_sub
                ET.SubElement(t_sub, "OutlineLevel").text = "4"
                ET.SubElement(t_sub, "Summary").text = "0"
                ET.SubElement(t_sub, "Duration").text = f"PT{dias * 8}H0M0S"
                ET.SubElement(t_sub, "Start").text = data_cursor.strftime(
                    "%Y-%m-%dT08:00:00"
                )
                ET.SubElement(t_sub, "Finish").text = data_fim.strftime(
                    "%Y-%m-%dT17:00:00"
                )

                data_cursor = data_fim
                task_id += 1

    tree = ET.ElementTree(project)
    ET.indent(tree, space="  ")
    tree.write(caminho_saida, encoding="utf-8", xml_declaration=True)
    print(
        f"\n✓ Cronograma gerado com sucesso para MS Project: {caminho_saida}"
    )


# ==============================================================================
# 5. EXPORTADOR DO MEMORIAL DE CÁLCULO PARA O EXCEL (.XLSX)
# ==============================================================================

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def exportar_memorial_excel_xlsx(obra):
    """Gera um arquivo Excel (.xlsx) com 2 abas interligadas por fórmulas:

    Aba 1: Resumo do Cronograma e Avanço Geral da Etapa
    Aba 2: Detalhamento Físico e Operacional das Subetapas
    """
    nome_obra = obra.get("nome", "Obra").replace(" ", "_")
    caminho_saida = f"Memorial_Planejamento_{nome_obra}.xlsx"

    # 1. PERGUNTA A LINHA INICIAL DO CRONOGRAMA
    limpar_terminal()
    print(
        f"=== EXPORTANDO MEMORIAL EXCEL (XLSX): {obra.get('nome').upper()} ===\n"
    )
    linha_cronograma_input = input(
        "Informe a linha inicial do Cronograma (ex: 1, 10, 15): "
    ).strip()
    try:
        linha_cronograma = int(linha_cronograma_input)
    except ValueError:
        linha_cronograma = 1
        print("⚠️ Linha inválida. Utilizando linha 1 por padrão.")

    # 2. CRIAÇÃO DO WORKBOOK EXCEL
    wb = openpyxl.Workbook()

    # Configuração de Estilos (Cabeçalhos e Bordas)
    fonte_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill_header = PatternFill(
        start_color="1F4E79", end_color="1F4E79", fill_type="solid"
    )
    borda_fina = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    alinhamento_centro = Alignment(horizontal="center", vertical="center")

    # ==========================================================================
    # ABA 2: DETALHAMENTO DE SUBETAPAS (CRIADA PRIMEIRO PARA RECEBER OS DADOS)
    # ==========================================================================
    ws2 = wb.active
    ws2.title = "Detalhamento Subetapas"

    headers_aba2 = [
        "Disciplina",  # A (Auxiliar para proc/soma)
        "Etapa",  # B (Auxiliar para proc/soma)
        "SubEtapa",  # C
        "Quantidade Física",  # D
        "Und",  # E
        "Produtividade (Eqp/Dia)",  # F
        "Quantidade de Equipes",  # G
        "Duração Estimada (Dias)",  # H
        "Dia de Início",  # I
        "Quantidade Executada",  # J
        "Avanço Subetapa (%)",  # K
        "Observação / Impedimento",  # L
    ]

    ws2.append(headers_aba2)

    # Estiliza cabeçalho da Aba 2
    for col in range(1, len(headers_aba2) + 1):
        cell = ws2.cell(row=1, column=col)
        cell.font = fonte_header
        cell.fill = fill_header
        cell.alignment = alinhamento_centro

    disciplinas = obra.get("disciplinas", {})
    linha_aba2 = 2
    mapa_etapas_linhas = {}  # Guarda as linhas inicial/final de cada etapa

    for disc, etapas in disciplinas.items():
        for etapa, subetapas in etapas.items():
            linha_inicio_etapa = linha_aba2

            for sub in subetapas:
                if isinstance(sub, dict):
                    nome_sub = sub.get("nome", "")
                    qtd = sub.get("quantidade", 0.0)
                    und = sub.get("unidade", "un")
                    prod = sub.get("produtividade_equipe_dia", 1.0)
                    eqp = sub.get("equipes", 1)
                    inicio = sub.get("dia_inicio", 1)
                    executado = sub.get("quantidade_executada", 0.0)
                    obs = sub.get("observacao", "")
                else:
                    nome_sub = str(sub)
                    qtd, und, prod, eqp, inicio, executado, obs = (
                        0.0,
                        "un",
                        1.0,
                        1,
                        1,
                        0.0,
                        "",
                    )

                # Fórmulas da Aba 2:
                # Duracao (H) = ARRED.PARA.CIMA(Qtd / (Produtividade * Equipes))
                formula_duracao = f"=SE(F{linha_aba2}*G{linha_aba2}>0; ARRED.PARA.CIMA(D{linha_aba2}/(F{linha_aba2}*G{linha_aba2}); 0); 0)"
                # Avanço % (K) = Executado / Qtd Total
                formula_avanco_sub = (
                    f"=SE(D{linha_aba2}>0; J{linha_aba2}/D{linha_aba2}; 0)"
                )

                linha_dados = [
                    disc,
                    etapa,
                    nome_sub,
                    qtd,
                    und,
                    prod,
                    eqp,
                    formula_duracao,
                    inicio,
                    executado,
                    formula_avanco_sub,
                    obs,
                ]

                ws2.append(linha_dados)

                # Formatações específicas de célula
                ws2.cell(row=linha_aba2, column=11).number_format = "0.0%"
                for c in range(1, len(headers_aba2) + 1):
                    ws2.cell(row=linha_aba2, column=c).border = borda_fina

                linha_aba2 += 1

            linha_fim_etapa = linha_aba2 - 1
            chave_etapa = f"{disc}||{etapa}"
            mapa_etapas_linhas[chave_etapa] = (
                linha_inicio_etapa,
                linha_fim_etapa,
            )

    # ==========================================================================
    # ABA 1: RESUMO DO CRONOGRAMA E ETAPAS
    # ==========================================================================
    ws1 = wb.create_sheet(title="Cronograma Geral", index=0)

    headers_aba1 = [
        "Linha do Cronograma",
        "Disciplina",
        "Etapa",
        "Avanço Geral da Etapa (%)",
    ]

    # Preenche espaço caso o usuário tenha informado uma linha > 1
    linha_atual_aba1 = 1
    while linha_atual_aba1 < linha_cronograma:
        ws1.append([])
        linha_atual_aba1 += 1

    ws1.append(headers_aba1)
    linha_header_aba1 = linha_atual_aba1

    # Estiliza cabeçalho da Aba 1
    for col in range(1, len(headers_aba1) + 1):
        cell = ws1.cell(row=linha_header_aba1, column=col)
        cell.font = fonte_header
        cell.fill = PatternFill(
            start_color="2F5597", end_color="2F5597", fill_type="solid"
        )
        cell.alignment = alinhamento_centro

    num_item_cronograma = 1
    linha_dados_aba1 = linha_header_aba1 + 1

    for disc, etapas in disciplinas.items():
        for etapa in etapas.keys():
            chave = f"{disc}||{etapa}"

            if chave in mapa_etapas_linhas:
                l_ini, l_fim = mapa_etapas_linhas[chave]
                # Média ponderada/soma da % de avanço calculada na Aba 2 para esta etapa
                formula_avanco_geral = f"=SEERRO(SOMASE('Detalhamento Subetapas'!B{l_ini}:B{l_fim}; C{linha_dados_aba1}; 'Detalhamento Subetapas'!J{l_ini}:J{l_fim}) / SOMASE('Detalhamento Subetapas'!B{l_ini}:B{l_fim}; C{linha_dados_aba1}; 'Detalhamento Subetapas'!D{l_ini}:D{l_fim}); 0)"
            else:
                formula_avanco_geral = 0.0

            row_aba1 = [
                num_item_cronograma,
                disc,
                etapa,
                formula_avanco_geral,
            ]

            ws1.append(row_aba1)

            # Formatação de porcentagem e bordas na Aba 1
            cell_pct = ws1.cell(row=linha_dados_aba1, column=4)
            cell_pct.number_format = "0.0%"
            cell_pct.alignment = alinhamento_centro

            ws1.cell(row=linha_dados_aba1, column=1).alignment = (
                alinhamento_centro
            )

            for c in range(1, 5):
                ws1.cell(row=linha_dados_aba1, column=c).border = borda_fina

            num_item_cronograma += 1
            linha_dados_aba1 += 1

    # Adjust auto-width das colunas para ambas as abas
    for ws in [ws1, ws2]:
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # 3. SALVAMENTO DO ARQUIVO .XLSX
    wb.save(caminho_saida)
    print(
        f"\n✓ Memorial em Excel com 2 abas gerado com sucesso: {caminho_saida}"
    )


# ==============================================================================
# 6. MENU PRINCIPAL DO MÓDULO DE PLANEJAMENTO
# ==============================================================================

def menu_planejamento_obra():
    """Sub-menu principal para seleção, parametrização e exportação de relatórios."""
    while True:
        obra_atual = selecionar_obra()
        if not obra_atual:
            break

        while True:
            limpar_terminal()
            print(
                f"=== PLANEJAMENTO & ENGENHARIA: {obra_atual['nome'].upper()} ===\n"
            )
            print("1. Preencher Parâmetros e Quantitativos das Subetapas")
            print("2. Exportar Cronograma para o MS Project (.xml)")
            print("3. Exportar Memorial de Cálculo para o Excel (.csv)")
            print("0. Selecionar Outra Obra\n")

            op = input("Escolha uma opção: ").strip()

            if op == "1":
                cadastrar_parametros_subetapas(obra_atual)
            elif op == "2":
                exportar_cronograma_ms_project(obra_atual)
                input("\nPressione Enter para continuar...")
            elif op == "3":
                exportar_memorial_excel_csv(obra_atual)
                input("\nPressione Enter para continuar...")
            elif op == "0":
                break
            else:
                input(
                    "\nOpção inválida! Pressione Enter para tentar novamente..."
                )