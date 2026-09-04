"""
Utilitários de cálculo de custos, partilhados entre vistas.
"""


def dias_tarefa(tarefa):
    if not tarefa.data_inicio or not tarefa.data_fim:
        return 0
    return (tarefa.data_fim - tarefa.data_inicio).days + 1


def custo_alocacao(alocacao):
    """Custo de uma alocação = % alocação * custo/dia do perfil da pessoa * dias da tarefa."""
    tarefa = alocacao.tarefa
    pessoa = alocacao.pessoa
    if not tarefa or not pessoa or not pessoa.perfil:
        return 0
    dias = dias_tarefa(tarefa)
    pct = float(alocacao.percentagem or 0) / 100
    custo_dia = float(pessoa.perfil.custo_dia or 0)
    return dias * pct * custo_dia


def custo_tarefa(tarefa):
    return sum(custo_alocacao(a) for a in tarefa.alocacoes)


def custo_projeto(projeto):
    return sum(custo_tarefa(t) for t in projeto.tarefas)
