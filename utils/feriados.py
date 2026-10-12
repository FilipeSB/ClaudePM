"""
Gestão de feriados: importação automática a partir da internet (API pública
e gratuita, sem necessidade de chave) e utilitários de marcação no calendário.
"""
from datetime import date, datetime

API_FERIADOS = "https://date.nager.at/api/v3/PublicHolidays/{ano}/{pais}"


def importar_feriados_internet(session, ano: int, pais: str = "PT"):
    """
    Vai buscar os feriados públicos de um país/ano à internet e grava-os
    (sem duplicar -- atualiza a descrição se a data já existir).
    Devolve o nº de feriados importados. Lança excepção se não conseguir
    ligar à internet (sem ligação, API em baixo, etc.) -- quem chama deve
    mostrar esse erro ao utilizador.
    """
    import requests
    from database.models import Feriado

    resposta = requests.get(API_FERIADOS.format(ano=ano, pais=pais), timeout=10)
    resposta.raise_for_status()
    dados = resposta.json()

    n = 0
    for item in dados:
        data_feriado = datetime.strptime(item["date"], "%Y-%m-%d").date()
        descricao = item.get("localName") or item.get("name") or ""
        feriado = session.query(Feriado).filter_by(data=data_feriado).first()
        if feriado is None:
            feriado = Feriado(data=data_feriado)
            session.add(feriado)
        feriado.descricao = descricao
        n += 1
    session.commit()
    return n


PAISES_DISPONIVEIS = [
    ("PT", "Portugal"),
    ("ES", "Espanha"),
    ("BR", "Brasil"),
    ("FR", "França"),
    ("GB", "Reino Unido"),
    ("DE", "Alemanha"),
]
