"""
Utilitários de cálculo de custos e conversão horas <-> percentagem.

Os custos são calculados DIA A DIA, usando o custo do perfil em vigor em
cada dia (segundo o histórico de custos), e podem ser limitados até uma data
(só conta o trabalho até essa data, mesmo que a atividade continue depois).
"""
from datetime import timedelta, date as date_cls
from database.models import DATA_BASE_CUSTOS


def dias_uteis(inicio, fim):
    """Nº de dias úteis (Seg-Sex) entre duas datas, inclusive (cálculo direto, sem ciclo)."""
    if not inicio or not fim or fim < inicio:
        return 0
    total = (fim - inicio).days + 1
    semanas, resto = divmod(total, 7)
    uteis = semanas * 5
    dia_semana = inicio.weekday()
    for i in range(resto):
        if (dia_semana + i) % 7 < 5:
            uteis += 1
    return uteis


def dias_calendario(inicio, fim):
    if not inicio or not fim or fim < inicio:
        return 0
    return (fim - inicio).days + 1


def dias_no_intervalo(inicio, fim, categoria="8h_uteis"):
    if categoria == "24h_todos":
        return dias_calendario(inicio, fim)
    return dias_uteis(inicio, fim)


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
    if not tarefa or not tarefa.data_inicio or not tarefa.data_fim:
        return 0
    return dias_no_intervalo(tarefa.data_inicio, tarefa.data_fim, categoria)


# ---------------------------------------------------------------------------
# Histórico de custos dos perfis
# ---------------------------------------------------------------------------
def _historico_ordenado(perfil):
    return sorted(perfil.historico_custos, key=lambda h: (h.data_alteracao, h.id))


def custo_perfil_na_data(perfil, data_referencia=None):
    """(custo_hora, custo_dia) do perfil em vigor na data indicada."""
    if not perfil:
        return 0.0, 0.0
    if data_referencia is None:
        data_referencia = date_cls.today()
    historico = _historico_ordenado(perfil)
    if not historico:
        return float(perfil.custo_hora or 0), float(perfil.custo_dia or 0)
    candidatos = [h for h in historico if h.data_alteracao <= data_referencia]
    escolhido = candidatos[-1] if candidatos else historico[0]
    return float(escolhido.custo_hora or 0), float(escolhido.custo_dia or 0)


def _segmentos_de_custo(perfil):
    """
    Lista de (inicio, fim, custo_hora, custo_dia): períodos consecutivos em
    que o custo é constante. O primeiro começa "desde sempre" (None) e o
    último termina "para sempre" (None). Registos com a mesma data: vale o
    mais recente (maior id).
    """
    historico = _historico_ordenado(perfil)
    if not historico:
        return [(None, None, float(perfil.custo_hora or 0), float(perfil.custo_dia or 0))]
    colapsado = []
    for h in historico:
        if colapsado and colapsado[-1].data_alteracao == h.data_alteracao:
            colapsado[-1] = h
        else:
            colapsado.append(h)
    segmentos = []
    for i, h in enumerate(colapsado):
        ini = None if i == 0 else h.data_alteracao
        fim = None if i == len(colapsado) - 1 else colapsado[i + 1].data_alteracao - timedelta(days=1)
        segmentos.append((ini, fim, float(h.custo_hora or 0), float(h.custo_dia or 0)))
    return segmentos


def sincronizar_perfil_com_historico(perfil, hoje=None):
    """Atualiza o custo 'atual' do perfil para o valor em vigor hoje, segundo o histórico."""
    hoje = hoje or date_cls.today()
    historico = _historico_ordenado(perfil)
    if not historico:
        return
    validos = [h for h in historico if h.data_alteracao <= hoje]
    escolhido = validos[-1] if validos else historico[0]
    perfil.custo_hora = escolhido.custo_hora
    perfil.custo_dia = escolhido.custo_dia
    if escolhido.data_alteracao != DATA_BASE_CUSTOS:
        perfil.data_atualizacao = escolhido.data_alteracao


# ---------------------------------------------------------------------------
# Custos
# ---------------------------------------------------------------------------
def custo_alocacao(alocacao, ate_data=None):
    """
    Custo de uma alocação = soma, para cada período de custo constante do
    perfil, de (dias de trabalho no período x % alocação x custo/dia).
    Só conta o trabalho da atividade até 'ate_data' (inclusive), se indicada.
    """
    tarefa = alocacao.tarefa
    pessoa = alocacao.pessoa
    if not tarefa or not pessoa or not pessoa.perfil:
        return 0.0
    if not tarefa.data_inicio or not tarefa.data_fim:
        return 0.0
    categoria = alocacao.categoria or "8h_uteis"
    pct = float(alocacao.percentagem or 0) / 100
    inicio_t = tarefa.data_inicio
    fim_t = tarefa.data_fim if ate_data is None else min(tarefa.data_fim, ate_data)
    if fim_t < inicio_t:
        return 0.0
    total = 0.0
    for ini, fim, _custo_hora, custo_dia in _segmentos_de_custo(pessoa.perfil):
        s = inicio_t if ini is None else max(inicio_t, ini)
        e = fim_t if fim is None else min(fim_t, fim)
        if e < s:
            continue
        total += dias_no_intervalo(s, e, categoria) * pct * custo_dia
    return total


def custo_tarefa(tarefa, ate_data=None):
    return sum(custo_alocacao(a, ate_data) for a in tarefa.alocacoes)


def custo_projeto(projeto, ate_data=None):
    """Custo do projeto; com 'ate_data', só o trabalho realizado até essa data."""
    return sum(custo_tarefa(t, ate_data) for t in projeto.tarefas)
