"""
Utilitários de cálculo de custos e conversão horas <-> percentagem,
partilhados entre vistas.
"""
from datetime import timedelta


def dias_uteis(inicio, fim):
    """Número de dias úteis (Seg-Sex) entre duas datas, inclusive."""
    if not inicio or not fim or fim < inicio:
        return 0
    total = 0
    dia = inicio
    while dia <= fim:
        if dia.weekday() < 5:  # 0=Segunda ... 4=Sexta
            total += 1
        dia += timedelta(days=1)
    return total


def dias_calendario(inicio, fim):
    if not inicio or not fim or fim < inicio:
        return 0
    return (fim - inicio).days + 1


def horas_base_por_dia(categoria: str) -> int:
    """Nº de horas que correspondem a 100% de alocação, segundo a categoria."""
    return 24 if categoria == "24h_todos" else 8


def horas_para_percentagem(horas: float, categoria: str) -> float:
    base = horas_base_por_dia(categoria)
    if base == 0:
        return 0.0
    return round((float(horas or 0) / base) * 100, 2)


def percentagem_para_horas(percentagem: float, categoria: str) -> float:
    base = horas_base_por_dia(categoria)
    return round((float(percentagem or 0) / 100) * base, 2)


def dias_tarefa(tarefa, categoria: str = "8h_uteis"):
    """
    Nº de dias 'de trabalho' da tarefa, segundo a categoria da alocação:
      - "8h_uteis"  -> conta só dias úteis (Seg-Sex)
      - "24h_todos" -> conta todos os dias do calendário
    """
    if not tarefa or not tarefa.data_inicio or not tarefa.data_fim:
        return 0
    if categoria == "24h_todos":
        return dias_calendario(tarefa.data_inicio, tarefa.data_fim)
    return dias_uteis(tarefa.data_inicio, tarefa.data_fim)


def custo_alocacao(alocacao):
    """Custo de uma alocação = % alocação * custo/dia do perfil da pessoa * dias 'de trabalho' da tarefa."""
    tarefa = alocacao.tarefa
    pessoa = alocacao.pessoa
    if not tarefa or not pessoa or not pessoa.perfil:
        return 0
    categoria = alocacao.categoria or "8h_uteis"
    dias = dias_tarefa(tarefa, categoria)
    pct = float(alocacao.percentagem or 0) / 100
    custo_dia = float(pessoa.perfil.custo_dia or 0)
    return dias * pct * custo_dia


def custo_tarefa(tarefa):
    return sum(custo_alocacao(a) for a in tarefa.alocacoes)


def custo_projeto(projeto):
    return sum(custo_tarefa(t) for t in projeto.tarefas)
