"""
Ligação à base de dados SQLite e utilitários de inicialização, migração e backup.
"""
import os
import sys
import shutil
from datetime import datetime, date
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from database.models import DATA_BASE_CUSTOS, Base, Feriado, Perfil, PerfilCustoHistorico, EstadoProjeto, EstadoTarefa, ESTADOS_PROJETO, ESTADOS_TAREFA


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
    }
    with ENGINE.begin() as conn:
        for nome, definicao in novas_colunas.items():
            if nome not in colunas_existentes:
                conn.execute(text(f"ALTER TABLE alocacao ADD COLUMN {nome} {definicao}"))
        # (a antiga coluna "categoria" pode continuar a existir em bases de
        # dados vindas de versões anteriores; fica sem uso, sem problema)

    if "pessoa" in inspector.get_table_names():
        colunas_pessoa = {c["name"] for c in inspector.get_columns("pessoa")}
        if "cor" not in colunas_pessoa:
            with ENGINE.begin() as conn:
                conn.execute(text("ALTER TABLE pessoa ADD COLUMN cor VARCHAR(7)"))


def init_db():
    """Cria as tabelas em falta, migra o esquema e semeia os perfis CC01-CC07."""
    Base.metadata.create_all(ENGINE)
    _migrar_esquema()
    session = SessionLocal()
    try:
        if session.query(Perfil).count() == 0:
            for codigo, designacao, custo_hora in PERFIS_DEFAULT:
                perfil = Perfil(
                    codigo=codigo,
                    designacao=designacao,
                    custo_hora=custo_hora,
                    custo_dia=custo_hora * 8,
                )
                session.add(perfil)
                session.flush()
                session.add(PerfilCustoHistorico(
                    perfil_id=perfil.id,
                    custo_hora=perfil.custo_hora,
                    custo_dia=perfil.custo_dia,
                    data_alteracao=DATA_BASE_CUSTOS,
                ))
            session.commit()

        # Perfis já existentes (de uma versão anterior) que ainda não tenham
        # nenhum registo de histórico: cria-se um ponto de partida com o
        # custo atual, para que as consultas de custo por data funcionem.
        perfis_sem_historico = (
            session.query(Perfil)
            .filter(~Perfil.historico_custos.any())
            .all()
        )
        if perfis_sem_historico:
            for perfil in perfis_sem_historico:
                session.add(PerfilCustoHistorico(
                    perfil_id=perfil.id,
                    custo_hora=perfil.custo_hora,
                    custo_dia=perfil.custo_dia,
                    data_alteracao=DATA_BASE_CUSTOS,
                ))
            session.commit()

        # Semear os estados configuráveis de Projeto/Tarefa, se ainda não existirem.
        if session.query(EstadoProjeto).count() == 0:
            for i, nome in enumerate(ESTADOS_PROJETO):
                session.add(EstadoProjeto(nome=nome, ordem=i))
            session.commit()
        if session.query(EstadoTarefa).count() == 0:
            for i, nome in enumerate(ESTADOS_TAREFA):
                session.add(EstadoTarefa(nome=nome, ordem=i))
            session.commit()
    finally:
        session.close()

    _migrar_dados()


def _migrar_dados():
    """
    Migrações de DADOS (não de esquema), controladas por PRAGMA user_version
    para correrem uma única vez por base de dados.

    v1: o primeiro registo do histórico de custos de cada perfil (o custo
    inicial) passa a valer "desde sempre". Antes ficava com a data de
    instalação, o que fazia com que uma alteração de custo com data de
    vigência anterior a essa fosse ignorada nos cálculos.
    """
    with ENGINE.begin() as conn:
        versao = conn.execute(text("PRAGMA user_version")).scalar() or 0
    if versao < 1:
        session = SessionLocal()
        try:
            for perfil in session.query(Perfil).all():
                historico = sorted(perfil.historico_custos, key=lambda h: h.id)
                if historico:
                    historico[0].data_alteracao = DATA_BASE_CUSTOS
            session.commit()
        finally:
            session.close()
        with ENGINE.begin() as conn:
            conn.execute(text("PRAGMA user_version = 1"))


def listar_estados_projeto(session):
    """Nomes dos estados de projeto configurados, pela ordem definida."""
    return [e.nome for e in session.query(EstadoProjeto).order_by(EstadoProjeto.ordem).all()]


def listar_estados_tarefa(session):
    """Nomes dos estados de tarefa configurados, pela ordem definida."""
    return [e.nome for e in session.query(EstadoTarefa).order_by(EstadoTarefa.ordem).all()]


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


def validar_ficheiro_sqlite(caminho: str) -> bool:
    """Confirma que o ficheiro parece ser mesmo uma base de dados SQLite válida."""
    try:
        import sqlite3
        conn = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
        conn.execute("SELECT name FROM sqlite_master LIMIT 1")
        conn.close()
        return True
    except Exception:
        return False


def restaurar_backup(origem: str) -> str:
    """
    Substitui a base de dados atual pelo ficheiro 'origem' (um backup
    anteriormente criado). Antes de substituir, guarda uma cópia de
    segurança do estado atual (para o caso de o restauro ser enganado).
    Devolve o caminho dessa cópia de segurança.
    """
    if not validar_ficheiro_sqlite(origem):
        raise ValueError("O ficheiro selecionado não parece ser uma base de dados válida.")

    ENGINE.dispose()

    seguranca = os.path.join(PASTA_DADOS, f"antes_restauro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, seguranca)

    shutil.copy2(origem, DB_PATH)

    # Garante que a BD restaurada fica com o esquema atualizado (caso seja
    # um backup antigo) e que os perfis por defeito existem se faltarem.
    init_db()

    return seguranca


def listar_feriados(session, ano=None):
    """Lista de objetos Feriado, ordenados por data (opcionalmente só de um ano)."""
    query = session.query(Feriado)
    if ano is not None:
        query = query.filter(Feriado.data >= date(ano, 1, 1), Feriado.data <= date(ano, 12, 31))
    return query.order_by(Feriado.data).all()


def conjunto_datas_feriados(session):
    """Set de datas (date) de todos os feriados -- para verificação rápida."""
    return {f.data for f in session.query(Feriado).all()}
