from datetime import datetime, timedelta


def gerar_cronograma_gantt(obra, data_inicio_obra_str="2026-11-10"):
    """Calcula as datas encadeadas e exibe o gráfico de Gantt simplificado."""
    data_atual = datetime.strptime(data_inicio_obra_str, "%Y-%m-%d")

    print(f"\n==================================================")
    print(f"   CRONOGRAMA FÍSICO DE EXECUÇÃO (GANTT)")
    print(f"   OBRA: {obra['nome'].upper()}")
    print(f"   INÍCIO GERAL: {data_atual.strftime('%d/%m/%Y')}")
    print(f"==================================================\n")

    disciplinas = obra.get("disciplinas", {})

    print(
        f"{'ITEM / SUBETAPA':<30} | {'INÍCIO':<10} | {'FIM':<10} | {'DIAS':<4} | 'VISUALIZADOR GANTT'"
    )
    print("-" * 80)

    for disc, etapas in disciplinas.items():
        print(f"\n[{disc.upper()}]")

        for etapa, subetapas in etapas.items():
            print(f"  > {etapa}")

            for sub in subetapas:
                if isinstance(sub, dict):
                    nome = sub.get("nome")
                    qtd = sub.get("quantidade", 0)
                    prod = sub.get("produtividade_equipe_dia", 1)
                    dias = (
                        int(qtd / prod) + (1 if (qtd % prod) != 0 else 0)
                        if prod > 0
                        else 1
                    )

                    data_fim = data_atual + timedelta(days=dias)

                    # Barra visual do Gantt
                    barra = "█" * min(dias, 20)

                    inicio_txt = data_atual.strftime("%d/%m/%Y")
                    fim_txt = data_fim.strftime("%d/%m/%Y")

                    print(
                        f"    🔹 {nome:<23} | {inicio_txt} | {fim_txt} | {dias:<4} | {barra}"
                    )

                    # Avança a data para a próxima subetapa (Caminho crítico sequencial)
                    data_atual = data_fim
                else:
                    print(
                        f"    🔹 {sub:<23} | --/--/---- | --/--/---- | --   | (Sem dados)"
                    )