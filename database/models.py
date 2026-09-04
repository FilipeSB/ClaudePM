"""
Modelos de dados (SQLAlchemy ORM) para a aplicação de Gestão de Pessoas e Projetos.
"""
from datetime import date
from sqlalchemy import (
    Column, Integer, String, Text, Date, Boolean, Numeric, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------
class Cliente(Base):
    __tablename__ = "cliente"

    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    contacto = Column(String(200))
    ativo = Column(Boolean, default=True)

    projetos = relationship("Projeto", back_populates="cliente", cascade="all, delete-orphan")

    def __repr__(self):
        return self.nome


# ---------------------------------------------------------------------------
# Equipa
# ---------------------------------------------------------------------------
class Equipa(Base):
    __tablename__ = "equipa"

    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    descricao = Column(Text)

    pessoas = relationship("Pessoa", back_populates="equipa")

    def __repr__(self):
        return self.nome


# ---------------------------------------------------------------------------
# Perfil (CC01 .. CC07)
# ---------------------------------------------------------------------------
class Perfil(Base):
    __tablename__ = "perfil"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(10), nullable=False, unique=True)   # "CC01".."CC07"
    designacao = Column(String(100))
    custo_hora = Column(Numeric(10, 2), default=0)
    custo_dia = Column(Numeric(10, 2), default=0)
    data_atualizacao = Column(Date, default=date.today)

    pessoas = relationship("Pessoa", back_populates="perfil")

    def __repr__(self):
        return f"{self.codigo} - {self.designacao}"


# ---------------------------------------------------------------------------
# Pessoa
# ---------------------------------------------------------------------------
class Pessoa(Base):
    __tablename__ = "pessoa"

    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    equipa_id = Column(Integer, ForeignKey("equipa.id"))
    perfil_id = Column(Integer, ForeignKey("perfil.id"))
    email = Column(String(200))
    ativo = Column(Boolean, default=True)

    equipa = relationship("Equipa", back_populates="pessoas")
    perfil = relationship("Perfil", back_populates="pessoas")
    alocacoes = relationship("Alocacao", back_populates="pessoa", cascade="all, delete-orphan")

    def __repr__(self):
        return self.nome


# ---------------------------------------------------------------------------
# Projeto
# ---------------------------------------------------------------------------
ESTADOS_PROJETO = ["Planeado", "Em curso", "Concluído", "Cancelado", "Em pausa"]


class Projeto(Base):
    __tablename__ = "projeto"

    id = Column(Integer, primary_key=True)
    nome = Column(String(200), nullable=False)
    cliente_id = Column(Integer, ForeignKey("cliente.id"))
    data_inicio = Column(Date)
    data_fim = Column(Date)
    objetivos = Column(Text)
    estado = Column(String(50), default="Planeado")

    cliente = relationship("Cliente", back_populates="projetos")
    tarefas = relationship("Tarefa", back_populates="projeto", cascade="all, delete-orphan")

    def __repr__(self):
        return self.nome


# ---------------------------------------------------------------------------
# Tarefa (atividade)
# ---------------------------------------------------------------------------
ESTADOS_TAREFA = ["Não iniciada", "Em curso", "Concluída", "Atrasada"]


class Tarefa(Base):
    __tablename__ = "tarefa"

    id = Column(Integer, primary_key=True)
    projeto_id = Column(Integer, ForeignKey("projeto.id"))
    nome = Column(String(200), nullable=False)
    data_inicio = Column(Date)
    data_fim = Column(Date)
    estado = Column(String(50), default="Não iniciada")

    projeto = relationship("Projeto", back_populates="tarefas")
    alocacoes = relationship("Alocacao", back_populates="tarefa", cascade="all, delete-orphan")

    def __repr__(self):
        return self.nome


# ---------------------------------------------------------------------------
# Alocacao (associativa Pessoa <-> Tarefa, com percentagem)
# ---------------------------------------------------------------------------
class Alocacao(Base):
    __tablename__ = "alocacao"

    id = Column(Integer, primary_key=True)
    pessoa_id = Column(Integer, ForeignKey("pessoa.id"))
    tarefa_id = Column(Integer, ForeignKey("tarefa.id"))
    percentagem = Column(Numeric(5, 2), default=0)  # 0-100
    data_inicio = Column(Date)
    data_fim = Column(Date)

    pessoa = relationship("Pessoa", back_populates="alocacoes")
    tarefa = relationship("Tarefa", back_populates="alocacoes")
