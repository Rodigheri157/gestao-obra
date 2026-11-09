from datetime import date, datetime, timedelta
from modulos_geral import ler_float, limpar_terminal

# Índices compatíveis com date.weekday(): 0 = Segunda ... 6 = Domingo
DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

CALENDARIO_PADRAO = {
    "nome": "Padrão Placore (Seg-Sáb, 8h/dia)",
    "dias_uteis": [0, 1, 2, 3, 4, 5],
    "horas_dia": 8.0,
    "feriados": [],
}


# ==============================================================================
# DATAS E CALENDÁRIO DE TRABALHO
# ==============================================================================

def converter_data(texto):
    """Converte 'AAAA-MM-DD' ou 'DD/MM/AAAA' em date. Retorna None se inválida."""
    texto = (texto or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def obter_calendario(projeto_obj):
    """Retorna o calendário do projeto, completando campos ausentes com o padrão Placore."""
    cal = dict(CALENDARIO_PADRAO)
    cal["feriados"] = []
    cal.update(projeto_obj.get("calendario", {}) if projeto_obj else {})
    return cal


def descrever_calendario(cal):
    """Resumo legível do calendário (ex.: 'Seg-Sáb | 8.0h/dia | 2 feriados')."""
    dias = ", ".join(DIAS_SEMANA[d] for d in sorted(cal["dias_uteis"])) or "nenhum"
    return f"Dias úteis: {dias} | {cal['horas_dia']}h/dia | {len(cal['feriados'])} feriado(s)/parada(s)"


def eh_dia_util(dia, cal):
    """Indica se a data é dia de trabalho no calendário informado."""
    return dia.weekday() in cal["dias_uteis"] and dia.isoformat() not in cal["feriados"]


def gerar_dias_uteis(data_inicio, quantidade, cal):
    """Lista as 'quantidade' primeiras datas úteis a partir de data_inicio (inclusive)."""
    if not cal["dias_uteis"]:
        raise ValueError("O calendário do projeto não possui dias úteis.")

    dias = []
    cursor = data_inicio
    while len(dias) < quantidade:
        if eh_dia_util(cursor, cal):
            dias.append(cursor)
        cursor += timedelta(days=1)
    return dias


def periodos_de_trabalho(horas_dia):
    """Divide a jornada em períodos (manhã 08:00-12:00 + tarde a partir das 13:00)."""
    inicio_manha = datetime(2000, 1, 1, 8, 0)
    if horas_dia <= 4:
        return [(inicio_manha, inicio_manha + timedelta(hours=horas_dia))]
    inicio_tarde = datetime(2000, 1, 1, 13, 0)
    return [
        (inicio_manha, datetime(2000, 1, 1, 12, 0)),
        (inicio_tarde, inicio_tarde + timedelta(hours=horas_dia - 4)),
    ]


# ==============================================================================
# MENU DE CONFIGURAÇÃO DO CALENDÁRIO DO PROJETO
# ==============================================================================

def menu_calendario(projeto_obj):
    """Edita o calendário do projeto. Retorna True se houve alteração a salvar."""
    cal = obter_calendario(projeto_obj)
    alterado = False

    while True:
        limpar_terminal()
        print(f"=== CALENDÁRIO DE TRABALHO: {projeto_obj['nome'].upper()} ===\n")
        print(f"  {descrever_calendario(cal)}")
        for feriado in cal["feriados"]:
            print(f"      • Feriado/parada: {converter_data(feriado).strftime('%d/%m/%Y')}")

        print("\n" + "-" * 50)
        print("1. Definir Dias Úteis da Semana")
        print("2. Definir Horas Trabalhadas por Dia")
        print("3. Adicionar Feriado / Parada Programada")
        print("4. Remover Feriado / Parada Programada")
        print("0. Voltar\n")

        op = input("Escolha uma opção: ").strip()

        if op == "1":
            atual = ",".join(str(d + 1) for d in cal["dias_uteis"])
            entrada = input(f"\nDias úteis (1=Seg, 2=Ter ... 6=Sáb, 7=Dom) separados por vírgula [{atual}]: ").strip()
            if entrada:
                try:
                    dias = sorted({int(x) - 1 for x in entrada.split(",") if x.strip()})
                except ValueError:
                    dias = []
                if dias and all(0 <= d <= 6 for d in dias):
                    cal["dias_uteis"] = dias
                    alterado = True
                else:
                    print("\n⚠️ Entrada inválida. Nenhuma alteração realizada.")
                    input("\nPressione Enter para continuar...")

        elif op == "2":
            horas = ler_float(f"\nHoras trabalhadas por dia [{cal['horas_dia']}]: ", valor_padrao=cal["horas_dia"])
            if 0 < horas <= 12:
                cal["horas_dia"] = horas
                alterado = True
            else:
                print("\n⚠️ Informe um valor entre 0 e 12 horas.")
                input("\nPressione Enter para continuar...")

        elif op == "3":
            dia = converter_data(input("\nData do feriado/parada (DD/MM/AAAA): "))
            if dia:
                if dia.isoformat() not in cal["feriados"]:
                    cal["feriados"] = sorted(cal["feriados"] + [dia.isoformat()])
                    alterado = True
            else:
                print("\n⚠️ Data inválida.")
                input("\nPressione Enter para continuar...")

        elif op == "4":
            if cal["feriados"]:
                for idx, feriado in enumerate(cal["feriados"], 1):
                    print(f"  {idx}. {converter_data(feriado).strftime('%d/%m/%Y')}")
                n = input("\nNúmero do feriado a remover: ").strip()
                if n.isdigit() and 1 <= int(n) <= len(cal["feriados"]):
                    cal["feriados"].pop(int(n) - 1)
                    alterado = True

        elif op == "0":
            break

    if alterado:
        cal["nome"] = f"Calendário {projeto_obj['nome']} ({len(cal['dias_uteis'])} dias/sem, {cal['horas_dia']}h/dia)"
        projeto_obj["calendario"] = cal
    return alterado
