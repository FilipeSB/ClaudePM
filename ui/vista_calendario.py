from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCalendarWidget, QComboBox, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QFormLayout
)
from PySide6.QtCore import QDate
from database.db import get_session
from database.models import Tarefa, Projeto, Cliente, Equipa, Pessoa, Alocacao, ESTADOS_TAREFA


class VistaCalendario(QWidget):
    """
    Calendário com filtros (cliente, projeto, equipa, pessoa, estado).
    Ao selecionar um dia, mostra as tarefas/atividades ativas nesse dia
    que cumprem os filtros escolhidos.
    """

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)

        # ---------------- Painel esquerdo: filtros + calendário ----------------
        esquerda = QVBoxLayout()

        filtros_box = QGroupBox("Filtros")
        filtros_form = QFormLayout()

        self.filtro_cliente = QComboBox()
        self.filtro_projeto = QComboBox()
        self.filtro_equipa = QComboBox()
        self.filtro_pessoa = QComboBox()
        self.filtro_estado = QComboBox()

        filtros_form.addRow("Cliente", self.filtro_cliente)
        filtros_form.addRow("Projeto", self.filtro_projeto)
        filtros_form.addRow("Equipa", self.filtro_equipa)
        filtros_form.addRow("Pessoa", self.filtro_pessoa)
        filtros_form.addRow("Estado", self.filtro_estado)
        filtros_box.setLayout(filtros_form)

        esquerda.addWidget(filtros_box)

        self.calendario = QCalendarWidget()
        self.calendario.setGridVisible(True)
        esquerda.addWidget(self.calendario)

        layout.addLayout(esquerda, 1)

        # ---------------- Painel direito: resultados do dia ----------------
        direita = QVBoxLayout()
        self.label_dia = QLabel()
        direita.addWidget(self.label_dia)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(6)
        self.tabela.setHorizontalHeaderLabels(
            ["Tarefa", "Projeto", "Cliente", "Estado", "Pessoas", "Datas"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        direita.addWidget(self.tabela)

        layout.addLayout(direita, 2)

        # eventos
        self.calendario.clicked.connect(self._atualizar_resultados)
        for combo in (self.filtro_cliente, self.filtro_projeto, self.filtro_equipa,
                      self.filtro_pessoa, self.filtro_estado):
            combo.currentIndexChanged.connect(self._atualizar_resultados)

        self._popular_filtros()
        self._atualizar_resultados()

    # ------------------------------------------------------------------
    def _popular_filtros(self):
        session = get_session()
        try:
            self.filtro_cliente.clear()
            self.filtro_cliente.addItem("Todos", None)
            for c in session.query(Cliente).order_by(Cliente.nome):
                self.filtro_cliente.addItem(c.nome, c.id)

            self.filtro_projeto.clear()
            self.filtro_projeto.addItem("Todos", None)
            for p in session.query(Projeto).order_by(Projeto.nome):
                self.filtro_projeto.addItem(p.nome, p.id)

            self.filtro_equipa.clear()
            self.filtro_equipa.addItem("Todas", None)
            for e in session.query(Equipa).order_by(Equipa.nome):
                self.filtro_equipa.addItem(e.nome, e.id)

            self.filtro_pessoa.clear()
            self.filtro_pessoa.addItem("Todas", None)
            for pe in session.query(Pessoa).order_by(Pessoa.nome):
                self.filtro_pessoa.addItem(pe.nome, pe.id)

            self.filtro_estado.clear()
            self.filtro_estado.addItem("Todos", None)
            for est in ESTADOS_TAREFA:
                self.filtro_estado.addItem(est, est)
        finally:
            session.close()

    def refresh_filtros(self):
        """Chamar quando dados de outras vistas mudarem (ex: novo cliente)."""
        self._popular_filtros()
        self._atualizar_resultados()

    # ------------------------------------------------------------------
    def _atualizar_resultados(self):
        dia_qdate = self.calendario.selectedDate()
        dia = dia_qdate.toPython()
        self.label_dia.setText(f"Atividades em {dia.strftime('%d/%m/%Y')}")

        cliente_id = self.filtro_cliente.currentData()
        projeto_id = self.filtro_projeto.currentData()
        equipa_id = self.filtro_equipa.currentData()
        pessoa_id = self.filtro_pessoa.currentData()
        estado = self.filtro_estado.currentData()

        session = get_session()
        try:
            query = session.query(Tarefa)
            tarefas = query.all()

            linhas = []
            for t in tarefas:
                if t.data_inicio is None or t.data_fim is None:
                    continue
                if not (t.data_inicio <= dia <= t.data_fim):
                    continue
                if estado and t.estado != estado:
                    continue
                if projeto_id and t.projeto_id != projeto_id:
                    continue
                if cliente_id and (not t.projeto or t.projeto.cliente_id != cliente_id):
                    continue

                pessoas_da_tarefa = [a.pessoa for a in t.alocacoes if a.pessoa]

                if pessoa_id and not any(p.id == pessoa_id for p in pessoas_da_tarefa):
                    continue
                if equipa_id and not any(p.equipa_id == equipa_id for p in pessoas_da_tarefa):
                    continue

                pessoas_txt = ", ".join(
                    f"{a.pessoa.nome} ({a.percentagem}%)" for a in t.alocacoes if a.pessoa
                )
                linhas.append([
                    t.nome,
                    t.projeto.nome if t.projeto else "",
                    t.projeto.cliente.nome if (t.projeto and t.projeto.cliente) else "",
                    t.estado,
                    pessoas_txt,
                    f"{t.data_inicio} a {t.data_fim}",
                ])

            self.tabela.setRowCount(len(linhas))
            for row, valores in enumerate(linhas):
                for col, valor in enumerate(valores):
                    self.tabela.setItem(row, col, QTableWidgetItem(str(valor)))
        finally:
            session.close()
