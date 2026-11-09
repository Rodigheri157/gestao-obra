import os
import shutil
from datetime import date, datetime
from modulos_calendario import converter_data
from modulos_geral import limpar_terminal, nome_subetapa, pasta_do_app, selecionar_item_lista
from modulos_obras import ARQUIVO_OBRAS, atualizar_quantidade_executada, salvar_obras

# Memorial de Cálculo e Avanço Físico em Excel, emitido POR ÁREA:
#   Aba 1 "Área e Etapas" : resumo por Obra > Disciplina > Etapa (datas, HH, valor, peso e avanço)
#   Aba 2 "Subetapas"      : campo de apontamento (qtd executada, início e término reais)
# A planilha sai protegida: só as células de apontamento (amarelas) aceitam edição.
# O mesmo arquivo, depois de preenchido em campo, é reimportado pelo app (importar_memorial_area).

try:
    import openpyxl
    from openpyxl.formatting.rule import DataBarRule, FormulaRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
    from openpyxl.workbook.protection import WorkbookProtection
    from openpyxl.worksheet.datavalidation import DataValidation

    EXCEL_DISPONIVEL = True
except ImportError:
    EXCEL_DISPONIVEL = False

DIRETORIO_ATUAL = pasta_do_app()
SENHA_PLANILHA = "placore"  # senha de proteção das abas (não é segurança forte; evita edição acidental)
VERSAO_LAYOUT = "2"

ABA_RESUMO = "Área e Etapas"
ABA_SUB = "Subetapas"
ABA_META = "_meta"

# Paleta Placore (Diretrizes Visuais PLACORE)
NAVY = "0F1D2E"
NAVY_2 = "203043"
GRAFITE = "3C485A"
LARANJA = "E14701"
DOURADO = "FAAD05"
DOURADO_SUAVE = "EDB260"
FUNDO = "EBE7E4"
FUNDO_QUENTE = "EFDCCE"
CINZA = "7D8189"
OFF_WHITE = "FCFAF8"
ENTRADA = "FFF2CC"        # amarelo claro: célula que recebe informação do usuário
ENTRADA_BORDA = "FAAD05"

# Colunas da Aba 2 (visíveis A:F, auxiliares ocultas G:J)
COL_DESC, COL_UND, COL_PREV, COL_EXEC, COL_INI, COL_FIM = "A", "B", "C", "D", "E", "F"
COL_ID, COL_CHAVE, COL_HH, COL_HH_EXEC = "G", "H", "I", "J"
CELULA_DATA_CORTE = "D5"   # data de corte da medição (Aba 2)
LINHA_CAB_SUB = 8          # cabeçalho da tabela da Aba 2
LINHA_CAB_RES = 9          # cabeçalho da tabela da Aba 1


# ==============================================================================
# ESTILOS
# ==============================================================================

def _fill(cor):
    return PatternFill(start_color=cor, end_color=cor, fill_type="solid")


def _borda(cor="D6D1CC", estilo="thin"):
    lado = Side(style=estilo, color=cor)
    return Border(left=lado, right=lado, top=lado, bottom=lado)


def _fonte(tamanho=10, negrito=False, cor=GRAFITE, italico=False):
    return Font(name="Calibri", size=tamanho, bold=negrito, color=cor, italic=italico)


def _estilizar(cel, fonte=None, fill=None, borda=None, alinh=None, formato=None):
    if fonte:
        cel.font = fonte
    if fill:
        cel.fill = fill
    if borda:
        cel.border = borda
    if alinh:
        cel.alignment = alinh
    if formato:
        cel.number_format = formato


def _celula_entrada(cel, formato=None):
    """Célula editável pelo usuário: amarela, borda dourada e desbloqueada."""
    _estilizar(cel, fonte=_fonte(10, True, NAVY), fill=_fill(ENTRADA), borda=_borda(ENTRADA_BORDA),
               alinh=Alignment(horizontal="center", vertical="center"), formato=formato)
    cel.protection = Protection(locked=False)


def _cabecalho_documento(ws, titulo, ultima_col, col_direita, projeto_obj, area_nome):
    """Faixa navy com título + faixa laranja + bloco de metadados (padrão Placore)."""
    ws.sheet_view.showGridLines = False
    for col in range(1, ultima_col + 1):
        ws.cell(row=1, column=col).fill = _fill(NAVY)
        ws.cell(row=2, column=col).fill = _fill(LARANJA)
    ws.row_dimensions[1].height = 36
    ws.row_dimensions[2].height = 4

    ws["A1"] = f"PLACORE   |   {titulo}"
    _estilizar(ws["A1"], fonte=Font(name="Calibri", size=14, bold=True, color="FFFFFF"),
               alinh=Alignment(vertical="center", indent=1))

    meta = [
        ("Projeto", projeto_obj["nome"]),
        ("Cliente", projeto_obj.get("cliente") or "N/I"),
        ("Área", area_nome),
        ("Emissão", datetime.now().strftime("%d/%m/%Y %H:%M")),
    ]
    for i, (rot, val) in enumerate(meta):
        cel = ws.cell(row=3 + i // 2, column=1 if i % 2 == 0 else col_direita, value=f"{rot}:  {val}")
        _estilizar(cel, fonte=_fonte(10, True, NAVY), alinh=Alignment(vertical="center", indent=1 if i % 2 == 0 else 0))
    for lin in (3, 4):
        ws.row_dimensions[lin].height = 18


def _cabecalho_tabela(ws, linha, titulos, larguras=None):
    for col, titulo in enumerate(titulos, 1):
        cel = ws.cell(row=linha, column=col, value=titulo)
        _estilizar(cel, fonte=Font(name="Calibri", size=10, bold=True, color="FFFFFF"), fill=_fill(NAVY_2),
                   borda=_borda(NAVY_2), alinh=Alignment(horizontal="center", vertical="center", wrap_text=True))
    ws.row_dimensions[linha].height = 32
    if larguras:
        for letra, largura in larguras.items():
            ws.column_dimensions[letra].width = largura




def _proteger(ws):
    ws.protection.sheet = True
    ws.protection.password = SENHA_PLANILHA
    ws.protection.selectLockedCells = False
    ws.protection.selectUnlockedCells = False
    ws.protection.formatColumns = True   # True = bloqueado (impede reexibir as colunas auxiliares)
    ws.protection.formatRows = True
    ws.protection.insertRows = True
    ws.protection.deleteRows = True
    ws.protection.sort = True
    ws.protection.autoFilter = True


# ==============================================================================
# DADOS DA ÁREA
# ==============================================================================

def obras_da_area(projeto_obj, obras, area_nome):
    """Obras da área com subetapas lançadas, na ordem cadastrada no projeto."""
    ordem = projeto_obj.get("areas", {}).get(area_nome, [])
    lista = [ob for ob in obras if ob.get("projeto_nome") == projeto_obj["nome"]
             and ob.get("area_nome") == area_nome and ob.get("disciplinas")]
    lista.sort(key=lambda ob: ordem.index(ob["obra_nome"]) if ob["obra_nome"] in ordem else len(ordem))
    return lista


def hh_subetapa(sub, horas_dia):
    """HH planejado = duração (dias úteis) x horas/dia x pessoas (equipe básica x nº de equipes)."""
    pax = sum(sub.get("equipe_basica", {}).values()) * sub.get("quantidade_equipes", 1)
    return sub.get("duracao_dias_planejada", 1) * horas_dia * pax


def _data_ou_none(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        return converter_data(valor)
    return None


# ==============================================================================
# EXPORTAÇÃO
# ==============================================================================

def nome_arquivo_memorial(projeto_obj, area_nome):
    base = f"Memorial_{projeto_obj['nome']}_{area_nome}".replace(" ", "_").replace("/", "-")
    return f"{base}.xlsx"


def exportar_memorial_area(projeto_obj, area_nome, obras, cron, resumo, valor_hh):
    """Gera o memorial da área (.xlsx, 2 abas, protegido). Retorna o caminho ou None."""
    if not EXCEL_DISPONIVEL:
        print("\n❌ A biblioteca 'openpyxl' não está instalada. Instale via terminal: pip install openpyxl")
        return None

    obras_area = obras_da_area(projeto_obj, obras, area_nome)
    if not obras_area:
        print(f"\n❌ A área '{area_nome}' não possui obras com subetapas cadastradas.")
        return None

    horas_dia = resumo["calendario"]["horas_dia"]
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = ABA_RESUMO
    ws2 = wb.create_sheet(ABA_SUB)
    wsm = wb.create_sheet(ABA_META)

    # ------------------------------------------------------------------ ABA 2
    _cabecalho_documento(ws2, "APONTAMENTO DE AVANÇO FÍSICO — SUBETAPAS", 6, 3, projeto_obj, area_nome)
    ws2.row_dimensions[5].height = 22
    _estilizar(ws2.cell(row=5, column=1, value="DATA DE CORTE DA MEDIÇÃO  ►"), fonte=_fonte(10, True, NAVY),
               alinh=Alignment(horizontal="right", vertical="center"))
    ws2.merge_cells("A5:C5")
    _celula_entrada(ws2[CELULA_DATA_CORTE], "DD/MM/YYYY")
    _estilizar(ws2.cell(row=5, column=5, value="data em que as quantidades foram medidas"),
               fonte=_fonte(9, False, CINZA, italico=True), alinh=Alignment(vertical="center", indent=1))
    _estilizar(ws2.cell(row=6, column=1, value="células em amarelo = preenchimento pelo usuário; demais células bloqueadas"),
               fonte=_fonte(9, False, CINZA, italico=True), alinh=Alignment(horizontal="right", vertical="center"))
    ws2.merge_cells("A6:C6")
    _estilizar(ws2["D6"], fill=_fill(ENTRADA), borda=_borda(ENTRADA_BORDA))

    _cabecalho_tabela(
        ws2, LINHA_CAB_SUB,
        ["DESCRIÇÃO", "UND", "QTD PREVISTA", "QTD EXECUTADA\n(ACUMULADA)", "INÍCIO REAL", "TÉRMINO REAL",
         "ID", "CHAVE", "HH", "HH EXEC"],
        {"A": 52, "B": 8, "C": 14, "D": 16, "E": 14, "F": 14},
    )
    for letra in (COL_ID, COL_CHAVE, COL_HH, COL_HH_EXEC):
        ws2.column_dimensions[letra].hidden = True

    linha = LINHA_CAB_SUB + 1
    etapas = []  # (wbs, obra, disc, etapa, subs, chave)
    faixa_dados = []
    zebra = False
    for n_ob, ob in enumerate(obras_area, 1):
        # Faixa da obra
        cel = ws2.cell(row=linha, column=1, value=f"{n_ob}  {ob['obra_nome'].upper()}")
        for col in range(1, 7):
            _estilizar(ws2.cell(row=linha, column=col), fill=_fill(NAVY), borda=_borda(NAVY))
        cel.font = Font(name="Calibri", size=11, bold=True, color=DOURADO)
        ws2.row_dimensions[linha].height = 20
        linha += 1
        for n_disc, (disc, etapas_disc) in enumerate(ob["disciplinas"].items(), 1):
            for n_et, (etapa, subs) in enumerate(etapas_disc.items(), 1):
                wbs = f"{n_ob}.{n_disc}.{n_et}"
                chave = f"{ob['obra_nome']}|{disc}|{etapa}"
                etapas.append((wbs, ob["obra_nome"], disc, etapa, subs, chave))
                # Faixa da etapa
                cel = ws2.cell(row=linha, column=1, value=f"{wbs}  {disc} › {etapa}")
                for col in range(1, 7):
                    _estilizar(ws2.cell(row=linha, column=col), fill=_fill(FUNDO_QUENTE), borda=_borda())
                cel.font = _fonte(10, True, NAVY)
                linha += 1
                for sub in subs:
                    zebra = not zebra
                    fundo = _fill(OFF_WHITE if zebra else "F4F1EE")
                    ini = converter_data(sub.get("inicio_real") or "")
                    fim = converter_data(sub.get("termino_real") or "")
                    valores = {
                        COL_DESC: nome_subetapa(sub),
                        COL_UND: sub.get("unidade", "un"),
                        COL_PREV: sub.get("quantidade_fisica", 0.0),
                        COL_EXEC: sub.get("quantidade_executada", 0.0),
                        COL_INI: ini,
                        COL_FIM: fim,
                        COL_ID: sub["id"],
                        COL_CHAVE: chave,
                        COL_HH: round(hh_subetapa(sub, horas_dia), 2),
                        COL_HH_EXEC: f"=IF({COL_PREV}{linha}>0,MIN(1,N({COL_EXEC}{linha})/{COL_PREV}{linha}),0)*{COL_HH}{linha}",
                    }
                    for letra, valor in valores.items():
                        ws2[f"{letra}{linha}"] = valor
                    for letra in (COL_DESC, COL_UND, COL_PREV):
                        _estilizar(ws2[f"{letra}{linha}"], fonte=_fonte(10), fill=fundo, borda=_borda())
                    ws2[f"{COL_DESC}{linha}"].alignment = Alignment(indent=2, vertical="center")
                    ws2[f"{COL_UND}{linha}"].alignment = Alignment(horizontal="center", vertical="center")
                    ws2[f"{COL_PREV}{linha}"].number_format = "#,##0.00"
                    _celula_entrada(ws2[f"{COL_EXEC}{linha}"], "#,##0.00")
                    _celula_entrada(ws2[f"{COL_INI}{linha}"], "DD/MM/YYYY")
                    _celula_entrada(ws2[f"{COL_FIM}{linha}"], "DD/MM/YYYY")
                    faixa_dados.append(linha)
                    linha += 1
    ultima_sub = linha - 1
    primeira_sub = LINHA_CAB_SUB + 1

    # Validações de entrada
    dv_qtd = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True,
                            showErrorMessage=True, errorTitle="Valor inválido",
                            error="Informe a quantidade executada ACUMULADA (número maior ou igual a zero).")
    dv_data = DataValidation(type="date", operator="between", formula1="DATE(2000,1,1)",
                             formula2="DATE(2100,12,31)", allow_blank=True, showErrorMessage=True,
                             errorTitle="Data inválida", error="Informe uma data válida (DD/MM/AAAA).")
    dv_fim = DataValidation(type="custom", formula1=f"OR({COL_FIM}{primeira_sub}=\"\",AND(ISNUMBER({COL_FIM}{primeira_sub}),"
                            f"OR({COL_INI}{primeira_sub}=\"\",{COL_FIM}{primeira_sub}>={COL_INI}{primeira_sub})))",
                            allow_blank=True, showErrorMessage=True, errorTitle="Término inválido",
                            error="O término real deve ser uma data igual ou posterior ao início real.")
    for dv in (dv_qtd, dv_data, dv_fim):
        ws2.add_data_validation(dv)
    for lin in faixa_dados:
        dv_qtd.add(f"{COL_EXEC}{lin}")
        dv_data.add(f"{COL_INI}{lin}")
        dv_fim.add(f"{COL_FIM}{lin}")
    dv_data.add(CELULA_DATA_CORTE)

    # Destaque: executado acima do previsto (laranja)
    ws2.conditional_formatting.add(
        f"{COL_EXEC}{primeira_sub}:{COL_EXEC}{ultima_sub}",
        FormulaRule(formula=[f"AND(ISNUMBER({COL_ID}{primeira_sub}),{COL_EXEC}{primeira_sub}>{COL_PREV}{primeira_sub})"],
                    fill=_fill("F8CBAD"), font=Font(color=LARANJA, bold=True)),
    )
    ws2.freeze_panes = f"A{LINHA_CAB_SUB + 1}"

    # ------------------------------------------------------------------ ABA 1
    titulos = ["EAP", "OBRA / DISCIPLINA", "ETAPA", "INÍCIO\nPREVISTO", "TÉRMINO\nPREVISTO", "DURAÇÃO\n(DIAS ÚTEIS)",
               "HH\nPREVISTO", "VALOR\n(R$)", "PESO\n(%)", "AVANÇO\nFÍSICO (%)", "INÍCIO\nREAL", "TÉRMINO\nREAL"]
    _cabecalho_documento(ws1, "MEMORIAL DE CÁLCULO E AVANÇO FÍSICO — ÁREA E ETAPAS", len(titulos), 4,
                         projeto_obj, area_nome)

    # Cartões de indicadores (rótulo na linha 6, valor na 7). B7 = valor do HH, C7 = HH total da área.
    rng = lambda col: f"'{ABA_SUB}'!${col}${primeira_sub}:${col}${ultima_sub}"
    corte = f"'{ABA_SUB}'!{CELULA_DATA_CORTE}"
    kpis = [
        ("B", "B", "VALOR DO HH (R$/HH)", valor_hh, '"R$" #,##0.00', NAVY),
        ("C", "C", "HH PREVISTO DA ÁREA", f"=SUM({rng(COL_HH)})", "#,##0", NAVY),
        ("D", "F", "VALOR PREVISTO", "=C7*B7", '"R$" #,##0.00', NAVY),
        ("G", "I", "AVANÇO FÍSICO DA ÁREA", f"=IF(C7>0,SUM({rng(COL_HH_EXEC)})/C7,0)", "0.0%", LARANJA),
        ("J", "L", "DATA DE CORTE", f"=IF({corte}=\"\",\"(não informada)\",{corte})", "DD/MM/YYYY", NAVY),
    ]
    for c_ini, c_fim, rot, val, fmt, cor in kpis:
        ws1[f"{c_ini}6"] = rot
        ws1[f"{c_ini}7"] = val
        for lin in (6, 7):
            for col in range(ord(c_ini), ord(c_fim) + 1):
                _estilizar(ws1[f"{chr(col)}{lin}"], fill=_fill(NAVY_2 if lin == 6 else FUNDO), borda=_borda(NAVY_2))
        _estilizar(ws1[f"{c_ini}6"], fonte=Font(name="Calibri", size=8, bold=True, color=DOURADO_SUAVE),
                   alinh=Alignment(horizontal="center", vertical="center"))
        _estilizar(ws1[f"{c_ini}7"], fonte=_fonte(14, True, cor),
                   alinh=Alignment(horizontal="center", vertical="center"), formato=fmt)
        if c_ini != c_fim:
            ws1.merge_cells(f"{c_ini}6:{c_fim}6")
            ws1.merge_cells(f"{c_ini}7:{c_fim}7")
    ws1.row_dimensions[6].height = 16
    ws1.row_dimensions[7].height = 28

    _cabecalho_tabela(ws1, LINHA_CAB_RES, titulos,
                      {"A": 9, "B": 30, "C": 34, "D": 12, "E": 12, "F": 11, "G": 11, "H": 15,
                       "I": 9, "J": 12, "K": 12, "L": 12})

    linha = LINHA_CAB_RES + 1
    linhas_obra = []
    linhas_etapa = []
    obra_atual = None
    for wbs, obra_nome, disc, etapa, subs, chave in etapas:
        if obra_nome != obra_atual:
            obra_atual = obra_nome
            linhas_obra.append([linha, []])
            ws1.cell(row=linha, column=1, value=wbs.split(".")[0])
            ws1.cell(row=linha, column=2, value=obra_nome.upper())
            linha += 1
        c_et = [cron[s["id"]] for s in subs]
        inicio = min(c["inicio"] for c in c_et)
        termino = max(c["termino"] for c in c_et)
        duracao = max(c["ef"] for c in c_et) - min(c["es"] for c in c_et)
        crit = f"{rng(COL_CHAVE)},\"{chave.replace(chr(34), chr(34) * 2)}\""
        hh_f = f"SUMIFS({rng(COL_HH)},{crit})"
        valores = [
            wbs, disc, etapa, inicio, termino, duracao,
            f"={hh_f}",
            f"=G{linha}*$B$7",
            f"=IF($C$7>0,G{linha}/$C$7,0)",
            f"=IF(G{linha}>0,SUMIFS({rng(COL_HH_EXEC)},{crit})/G{linha},0)",
            f"=IFERROR(IF(_xlfn.MINIFS({rng(COL_INI)},{crit})=0,\"\",_xlfn.MINIFS({rng(COL_INI)},{crit})),\"\")",
            f"=IF(COUNTIFS({crit},{rng(COL_FIM)},\"\")>0,\"\",IFERROR(_xlfn.MAXIFS({rng(COL_FIM)},{crit}),\"\"))",
        ]
        for col, v in enumerate(valores, 1):
            ws1.cell(row=linha, column=col, value=v)
        linhas_obra[-1][1].append(linha)
        linhas_etapa.append(linha)
        linha += 1
    linha_total = linha

    # Linhas-resumo de obra (as etapas de cada obra ficam em linhas contíguas logo abaixo dela)
    def resumo_linha(lin, ini, fim):
        r = lambda col: f"{col}{ini}:{col}{fim}"
        ws1[f"D{lin}"] = f"=MIN({r('D')})"
        ws1[f"E{lin}"] = f"=MAX({r('E')})"
        ws1[f"G{lin}"] = f"=SUM({r('G')})"
        ws1[f"H{lin}"] = f"=G{lin}*$B$7"
        ws1[f"I{lin}"] = f"=IF($C$7>0,G{lin}/$C$7,0)"
        ws1[f"J{lin}"] = f"=IF(G{lin}>0,SUMPRODUCT({r('G')},{r('J')})/G{lin},0)"
        ws1[f"K{lin}"] = f"=IF(COUNT({r('K')})=0,\"\",MIN({r('K')}))"
        ws1[f"L{lin}"] = f"=IF(COUNTBLANK({r('L')})>0,\"\",MAX({r('L')}))"

    for lin_ob, filhas in linhas_obra:
        resumo_linha(lin_ob, filhas[0], filhas[-1])

    # Linha de total da área (soma das etapas; as linhas de obra são ignoradas pelos critérios)
    ws1.cell(row=linha_total, column=2, value=f"TOTAL DA ÁREA — {area_nome.upper()}")
    obras_ref = lambda col: ",".join(f"{col}{l}" for l, _ in linhas_obra)
    ws1[f"D{linha_total}"] = f"=MIN({obras_ref('D')})"
    ws1[f"E{linha_total}"] = f"=MAX({obras_ref('E')})"
    ws1[f"G{linha_total}"] = "=$C$7"
    ws1[f"H{linha_total}"] = f"=G{linha_total}*$B$7"
    ws1[f"I{linha_total}"] = f"=IF(G{linha_total}>0,1,0)"
    ws1[f"J{linha_total}"] = "=$G$7"
    ws1[f"K{linha_total}"] = f"=IF(COUNT({obras_ref('K')})=0,\"\",MIN({obras_ref('K')}))"
    ws1[f"L{linha_total}"] = (f"=IF(COUNTBLANK(L{LINHA_CAB_RES + 1}:L{linha_total - 1})>0,\"\","
                              f"MAX(L{LINHA_CAB_RES + 1}:L{linha_total - 1}))")

    # Formatação das linhas da Aba 1
    zebra = False
    for lin in range(LINHA_CAB_RES + 1, linha_total + 1):
        eh_obra = any(lin == l for l, _ in linhas_obra)
        eh_total = lin == linha_total
        if eh_total:
            fonte, fundo = Font(name="Calibri", size=11, bold=True, color="FFFFFF"), _fill(NAVY)
        elif eh_obra:
            fonte, fundo = _fonte(10, True, NAVY), _fill(FUNDO_QUENTE)
        else:
            zebra = not zebra
            fonte, fundo = _fonte(10), _fill(OFF_WHITE if zebra else "F4F1EE")
        for col in range(1, len(titulos) + 1):
            cel = ws1.cell(row=lin, column=col)
            _estilizar(cel, fonte=fonte, fill=fundo, borda=_borda(NAVY if eh_total else "D6D1CC"),
                       alinh=Alignment(horizontal="left" if col in (2, 3) else "center", vertical="center",
                                       indent=1 if col == 3 else 0))
        if eh_total:
            ws1.cell(row=lin, column=10).font = Font(name="Calibri", size=11, bold=True, color=DOURADO)
        for col, fmt in ((4, "DD/MM/YYYY"), (5, "DD/MM/YYYY"), (7, "#,##0"), (8, '"R$" #,##0.00'),
                         (9, "0.0%"), (10, "0.0%"), (11, "DD/MM/YYYY"), (12, "DD/MM/YYYY")):
            ws1.cell(row=lin, column=col).number_format = fmt
        ws1.row_dimensions[lin].height = 18

    # Barra de dados no avanço físico das etapas
    ws1.conditional_formatting.add(
        f"J{LINHA_CAB_RES + 1}:J{linha_total - 1}",
        DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color=DOURADO),
    )
    ws1.freeze_panes = f"A{LINHA_CAB_RES + 1}"
    nota = linha_total + 2
    _estilizar(ws1.cell(row=nota, column=1,
                        value="Avanço físico ponderado em HH: Σ(HH da subetapa × mín(1; executado/previsto)) ÷ Σ HH. "
                              "Peso = HH da etapa ÷ HH da área. Valor = HH × valor do HH. "
                              "Datas previstas = cronograma calculado pelo app; datas reais = apontamento da aba Subetapas."),
               fonte=_fonte(8, False, CINZA, italico=True))
    ws1.merge_cells(start_row=nota, start_column=1, end_row=nota, end_column=len(titulos))
    ws1.cell(row=nota, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws1.row_dimensions[nota].height = 28

    # ------------------------------------------------------------------ META (oculta)
    for chave, valor in (("versao", VERSAO_LAYOUT), ("projeto", projeto_obj["nome"]), ("area", area_nome),
                         ("emissao", datetime.now().isoformat(timespec="seconds")),
                         ("linha_inicial", primeira_sub), ("linha_final", ultima_sub)):
        wsm.append([chave, valor])
    wsm.sheet_state = "veryHidden"

    # Impressão
    for ws in (ws1, ws2):
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = f"{LINHA_CAB_RES if ws is ws1 else LINHA_CAB_SUB}:{LINHA_CAB_RES if ws is ws1 else LINHA_CAB_SUB}"
        ws.oddFooter.left.text = "PLACORE — Memorial de Cálculo e Avanço Físico"
        ws.oddFooter.right.text = "Página &P de &N"
        _proteger(ws)
    _proteger(wsm)
    wb.security = WorkbookProtection(workbookPassword=SENHA_PLANILHA, lockStructure=True)
    wb.active = 1  # abre na aba de apontamento

    caminho = os.path.join(DIRETORIO_ATUAL, nome_arquivo_memorial(projeto_obj, area_nome))
    try:
        wb.save(caminho)
    except PermissionError:
        print(f"\n❌ Não foi possível salvar '{os.path.basename(caminho)}': o arquivo está aberto no Excel? Feche e tente novamente.")
        return None
    return caminho


# ==============================================================================
# IMPORTAÇÃO DO MEMORIAL PREENCHIDO
# ==============================================================================

def analisar_memorial(caminho, projeto_obj, area_nome, obras, data_corte_padrao=None):
    """
    Lê o memorial preenchido e monta o plano de alterações (sem gravar).
    Retorna dict {data_corte, mudancas, avisos, erros, reconhecidas}.
    """
    wb = openpyxl.load_workbook(caminho, data_only=False)
    if ABA_SUB not in wb.sheetnames or ABA_META not in wb.sheetnames:
        raise ValueError("o arquivo não é um memorial emitido por este app (abas 'Subetapas'/'_meta' ausentes)")
    meta = {str(r[0]): r[1] for r in wb[ABA_META].iter_rows(values_only=True) if r and r[0] is not None}
    if meta.get("projeto") != projeto_obj["nome"] or meta.get("area") != area_nome:
        raise ValueError(f"o memorial é do projeto '{meta.get('projeto')}' / área '{meta.get('area')}', "
                         f"não de '{projeto_obj['nome']}' / '{area_nome}'")

    ws = wb[ABA_SUB]
    data_corte = _data_ou_none(ws[CELULA_DATA_CORTE].value)

    subs_area = {sub["id"]: sub for ob in obras_da_area(projeto_obj, obras, area_nome)
                 for etapas in ob["disciplinas"].values() for subs in etapas.values() for sub in subs}

    mudancas, avisos, erros = [], [], []
    reconhecidas = 0
    for lin in range(int(meta["linha_inicial"]), int(meta["linha_final"]) + 1):
        id_txt = ws[f"{COL_ID}{lin}"].value
        if id_txt is None:
            continue  # faixa de obra/etapa
        try:
            sid = int(id_txt)
        except (TypeError, ValueError):
            continue
        sub = subs_area.get(sid)
        if not sub:
            avisos.append(f"Linha {lin}: subetapa #{sid} não existe mais na área — ignorada.")
            continue
        reconhecidas += 1
        rotulo = f"#{sid} {nome_subetapa(sub)}"
        und = sub.get("unidade", "un")
        mud = {"sub": sub, "rotulo": rotulo, "exec": None, "ini": None, "fim": None}

        # Quantidade executada acumulada
        v_exec = ws[f"{COL_EXEC}{lin}"].value
        if v_exec not in (None, ""):
            try:
                novo = float(str(v_exec).replace(",", "."))
            except ValueError:
                erros.append(f"{rotulo}: quantidade executada inválida ('{v_exec}') — ignorada.")
                novo = None
            if novo is not None and novo < 0:
                erros.append(f"{rotulo}: quantidade executada negativa — ignorada.")
                novo = None
            atual = sub.get("quantidade_executada", 0.0)
            if novo is not None and abs(novo - atual) > 1e-9:
                mud["exec"] = (atual, novo)
                prev = sub.get("quantidade_fisica", 0.0)
                if novo > prev:
                    avisos.append(f"{rotulo}: executado ({novo} {und}) acima do previsto ({prev} {und}); "
                                  "o avanço será limitado a 100%.")
                if novo < atual:
                    avisos.append(f"{rotulo}: acumulado informado ({novo} {und}) MENOR que o atual ({atual} {und}).")

        # Datas reais
        datas = {}
        for chave, col, campo in (("ini", COL_INI, "inicio_real"), ("fim", COL_FIM, "termino_real")):
            bruto = ws[f"{col}{lin}"].value
            nova = _data_ou_none(bruto)
            if bruto not in (None, "") and nova is None:
                erros.append(f"{rotulo}: {'início' if chave == 'ini' else 'término'} real inválido ('{bruto}') — ignorado.")
                nova = converter_data(sub.get(campo) or "")
            datas[chave] = nova
            atual_dt = converter_data(sub.get(campo) or "")
            if nova != atual_dt:
                mud[chave] = (atual_dt, nova)
        if datas["ini"] and datas["fim"] and datas["fim"] < datas["ini"]:
            erros.append(f"{rotulo}: término real anterior ao início real — datas ignoradas.")
            mud["ini"] = mud["fim"] = None
        elif datas["fim"] and not datas["ini"] and not sub.get("inicio_real"):
            avisos.append(f"{rotulo}: término real informado sem início real.")
        if mud["exec"] and mud["exec"][1] > 0 and not datas["ini"]:
            avisos.append(f"{rotulo}: há quantidade executada mas o início real não foi informado.")

        if mud["exec"] or mud["ini"] or mud["fim"]:
            mudancas.append(mud)

    if any(m["exec"] for m in mudancas) and not data_corte:
        data_corte = data_corte_padrao
    return {"data_corte": data_corte, "mudancas": mudancas, "avisos": avisos, "erros": erros,
            "reconhecidas": reconhecidas, "meta": meta}


def aplicar_plano(plano):
    """Aplica as mudanças nas subetapas (em memória)."""
    data_iso = plano["data_corte"].isoformat() if plano["data_corte"] else None
    for m in plano["mudancas"]:
        sub = m["sub"]
        if m["exec"]:
            sub.setdefault("medicoes", [])
            mesma = [x for x in sub["medicoes"] if x["data"] == data_iso]
            if mesma:
                mesma[0]["acumulado"] = m["exec"][1]
            else:
                sub["medicoes"].append({"data": data_iso, "acumulado": m["exec"][1]})
            atualizar_quantidade_executada(sub)
        if m["ini"]:
            sub["inicio_real"] = m["ini"][1].isoformat() if m["ini"][1] else None
        if m["fim"]:
            sub["termino_real"] = m["fim"][1].isoformat() if m["fim"][1] else None


def _fmt(d):
    return d.strftime("%d/%m/%Y") if d else "-"


def importar_memorial_area(projeto_obj, area_nome, obras):
    """Seleciona o memorial preenchido, mostra a prévia e grava (com backup). Retorna True se gravou."""
    limpar_terminal()
    print(f"=== IMPORTAR MEMORIAL PREENCHIDO — ÁREA: {area_nome.upper()} ===\n")
    if not EXCEL_DISPONIVEL:
        input("❌ A biblioteca 'openpyxl' não está instalada (pip install openpyxl). Pressione Enter...")
        return False

    padrao = nome_arquivo_memorial(projeto_obj, area_nome)
    arquivos = sorted(f for f in os.listdir(DIRETORIO_ATUAL)
                      if f.lower().endswith(".xlsx") and f.startswith("Memorial_") and not f.startswith("~$"))
    arquivos.sort(key=lambda f: f != padrao)  # o memorial desta área primeiro
    arq, _ = selecionar_item_lista(arquivos + ["Informar outro caminho..."], titulo="Memorial (.xlsx)")
    if not arq:
        return False
    caminho = input("\nCaminho completo do .xlsx: ").strip().strip('"') if arq == "Informar outro caminho..." \
        else os.path.join(DIRETORIO_ATUAL, arq)
    if not os.path.isfile(caminho):
        input("\n❌ Arquivo não encontrado. Pressione Enter...")
        return False

    try:
        plano = analisar_memorial(caminho, projeto_obj, area_nome, obras)
    except (ValueError, KeyError, OSError) as e:
        input(f"\n❌ Não foi possível ler o memorial: {e}. Nada foi alterado. Pressione Enter...")
        return False
    except Exception as e:  # arquivo corrompido / não-xlsx
        input(f"\n❌ Arquivo inválido: {e}. Nada foi alterado. Pressione Enter...")
        return False

    # Data de corte: obrigatória quando há quantidade nova
    if any(m["exec"] for m in plano["mudancas"]) and not plano["data_corte"]:
        print("⚠️ A 'Data de corte da medição' não foi preenchida no memorial.")
        texto = input(f"Data da medição (DD/MM/AAAA) [{date.today():%d/%m/%Y}]: ").strip()
        plano["data_corte"] = converter_data(texto) if texto else date.today()
        if not plano["data_corte"]:
            input("\n❌ Data inválida. Nada foi alterado. Pressione Enter...")
            return False

    limpar_terminal()
    print(f"=== PRÉVIA DA IMPORTAÇÃO: {os.path.basename(caminho)} ===\n")
    print(f"Subetapas reconhecidas: {plano['reconhecidas']} | Com alteração: {len(plano['mudancas'])}")
    if plano["data_corte"]:
        print(f"Data de corte da medição: {plano['data_corte']:%d/%m/%Y}")
    print()
    for m in plano["mudancas"]:
        und = m["sub"].get("unidade", "un")
        print(f"  • {m['rotulo']}")
        if m["exec"]:
            prev = m["sub"].get("quantidade_fisica", 0.0)
            pct = min(1.0, m["exec"][1] / prev) * 100 if prev > 0 else 0.0
            print(f"      Executado acumulado: {m['exec'][0]} -> {m['exec'][1]} {und} ({pct:.1f}%)")
        if m["ini"]:
            print(f"      Início real: {_fmt(m['ini'][0])} -> {_fmt(m['ini'][1])}")
        if m["fim"]:
            print(f"      Término real: {_fmt(m['fim'][0])} -> {_fmt(m['fim'][1])}")
    if plano["avisos"]:
        print("\n--- AVISOS ---")
        for a in plano["avisos"]:
            print(f"  ⚠️ {a}")
    if plano["erros"]:
        print("\n--- VALORES DESCONSIDERADOS ---")
        for e in plano["erros"]:
            print(f"  ❌ {e}")

    if not plano["mudancas"]:
        input("\nNenhuma alteração a importar. Pressione Enter...")
        return False
    if input("\nConfirma a importação? (S/N): ").strip().upper() != "S":
        input("\nImportação cancelada. Nada foi alterado. Pressione Enter...")
        return False

    backup = ARQUIVO_OBRAS.replace(".json", f"_backup_{datetime.now():%Y%m%d_%H%M%S}.json")
    if os.path.exists(ARQUIVO_OBRAS):
        shutil.copy2(ARQUIVO_OBRAS, backup)
    aplicar_plano(plano)
    if salvar_obras(obras):
        input(f"\n✓ Avanços importados. Backup do estado anterior: {os.path.basename(backup)}. Pressione Enter...")
        return True
    input("\n❌ Falha ao salvar. Pressione Enter...")
    return False
