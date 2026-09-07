"""
Utilitários de navegação por período (Semanal / Mensal / Anual),
partilhados entre a vista de Calendário e a vista de Alocação.
"""
import calendar
from datetime import date, timedelta

PERIODOS = ["Semanal", "Mensal", "Anual"]


def inicio_semana(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())  # segunda-feira


def intervalo_periodo(periodo: str, referencia: date):
    """Devolve (data_inicio, data_fim) do período que contém 'referencia'."""
    if periodo == "Semanal":
        ini = inicio_semana(referencia)
        fim = ini + timedelta(days=6)
    elif periodo == "Anual":
        ini = date(referencia.year, 1, 1)
        fim = date(referencia.year, 12, 31)
    else:  # Mensal
        ini = date(referencia.year, referencia.month, 1)
        ultimo_dia = calendar.monthrange(referencia.year, referencia.month)[1]
        fim = date(referencia.year, referencia.month, ultimo_dia)
    return ini, fim


def periodo_seguinte(periodo: str, referencia: date) -> date:
    if periodo == "Semanal":
        return referencia + timedelta(days=7)
    if periodo == "Anual":
        return referencia.replace(year=referencia.year + 1)
    # Mensal
    if referencia.month == 12:
        return referencia.replace(year=referencia.year + 1, month=1)
    return referencia.replace(month=referencia.month + 1)


def periodo_anterior(periodo: str, referencia: date) -> date:
    if periodo == "Semanal":
        return referencia - timedelta(days=7)
    if periodo == "Anual":
        return referencia.replace(year=referencia.year - 1)
    # Mensal
    if referencia.month == 1:
        return referencia.replace(year=referencia.year - 1, month=12)
    return referencia.replace(month=referencia.month - 1)


def descricao_periodo(periodo: str, referencia: date) -> str:
    ini, fim = intervalo_periodo(periodo, referencia)
    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    if periodo == "Semanal":
        return f"{ini.day} {meses[ini.month-1]} a {fim.day} {meses[fim.month-1]} {fim.year}"
    if periodo == "Anual":
        return f"Ano {referencia.year}"
    return f"{meses[referencia.month-1]} {referencia.year}"


def dias_do_periodo(periodo: str, referencia: date):
    """Lista de todas as datas (date) dentro do período, dia a dia."""
    ini, fim = intervalo_periodo(periodo, referencia)
    dias = []
    d = ini
    while d <= fim:
        dias.append(d)
        d += timedelta(days=1)
    return dias


def meses_do_ano(ano: int):
    """Lista de (mes_numero, data_inicio_mes, data_fim_mes) para um ano."""
    resultado = []
    for mes in range(1, 13):
        ini = date(ano, mes, 1)
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        fim = date(ano, mes, ultimo_dia)
        resultado.append((mes, ini, fim))
    return resultado
