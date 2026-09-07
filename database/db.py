"""
Ligação à base de dados SQLite e utilitários de inicialização, migração e backup.
"""
import os
import sys
import shutil
from datetime import datetime
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from database.models import Base, Perfil


def _pasta_dados_utilizador() -> str:
    """
    Pasta onde ficam os dados da aplicação (dados.db), separada da pasta de
    instalação. Isto garante que, ao instalar uma versão nova por cima
    (reinstalar/atualizar), a base de dados existente NUNCA é apagada nem
    sobrescrita, porque o instalador só mexe nos ficheiros do programa.

    Windows: %APPDATA%\\GestaoProjetos
    Linux/Mac: ~/.gestao-projetos
    """
    nome_pasta = "GestaoProjetos"
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        pasta = os.path.join(base, nome_pasta)
    else:
        pasta = os.path.join(os.path.expanduser("~"), f".{nome_pasta.lower()}")
    os.makedirs(pasta, exist_ok=True)
    return pasta


PASTA_DADOS = _pasta_dados_utilizador()
DB_PATH = os.path.join(PASTA_DADOS, "dados.db")
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


def _migrar_esquema():
    """
    Migração leve: adiciona colunas novas a tabelas já existentes sem apagar
    dados. Corre sempre que a app arranca; é seguro correr repetidamente
    (verifica antes de tentar adicionar cada coluna).
    """
    inspector = inspect(ENGINE)
    if "alocacao" not in inspector.get_table_names():
        return  # tabela ainda não existe, será criada de raiz por create_all

    colunas_existentes = {c["name"] for c in inspector.get_columns("alocacao")}
    novas_colunas = {
        "tipo": "VARCHAR(20) DEFAULT 'percentagem'",
        "horas": "NUMERIC(5,2)",
        "categoria": "VARCHAR(20) DEFAULT '8h_uteis'",
    }
    with ENGINE.begin() as conn:
        for nome, definicao in novas_colunas.items():
            if nome not in colunas_existentes:
                conn.execute(text(f"ALTER TABLE alocacao ADD COLUMN {nome} {definicao}"))


def init_db():
    """Cria as tabelas em falta, migra o esquema e semeia os perfis CC01-CC07."""
    Base.metadata.create_all(ENGINE)
    _migrar_esquema()
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


def fazer_backup(destino: str) -> str:
    """Copia o ficheiro dados.db atual para o caminho 'destino'. Devolve o caminho final."""
    ENGINE.dispose()  # garante que não há escrita pendente por fazer
    shutil.copy2(DB_PATH, destino)
    return destino


def nome_sugerido_backup() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"backup_gestao_projetos_{timestamp}.db"
