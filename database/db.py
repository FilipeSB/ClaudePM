"""
Ligação à base de dados SQLite e utilitários de inicialização.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Perfil

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dados.db")
ENGINE = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=ENGINE)

PERFIS_DEFAULT = [
    ("CC01", "Estagiário", 10),
    ("CC02", "Júnior", 15),
    ("CC03", "Júnior Sénior", 20),
    ("CC04", "Pleno", 28),
    ("CC05", "Sénior", 38),
    ("CC06", "Especialista", 50),
    ("CC07", "Consultor Principal", 65),
]


def init_db():
    """Cria as tabelas (se não existirem) e semeia os perfis CC01-CC07."""
    Base.metadata.create_all(ENGINE)
    session = SessionLocal()
    try:
        if session.query(Perfil).count() == 0:
            for codigo, designacao, custo_hora in PERFIS_DEFAULT:
                session.add(Perfil(
                    codigo=codigo,
                    designacao=designacao,
                    custo_hora=custo_hora,
                    custo_dia=custo_hora * 8,
                ))
            session.commit()
    finally:
        session.close()


def get_session():
    return SessionLocal()
