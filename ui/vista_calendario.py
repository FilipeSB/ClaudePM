from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QFormLayout,
    QProgressBar, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

from database.db import get_session
from database.models import Tarefa, Projeto, Cliente, Pessoa, ESTADOS_TAREFA
from utils.periodos import (
    PERIODOS, intervalo_periodo, periodo_seguinte, periodo_anterior,
    descricao_periodo, dias_do_periodo, meses_do_ano,
)
from utils.exportacao import exportar_excel, exportar_pdf

DIAS_SEMANA_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _cor_percentagem(pct: float):
    if pct <= 0:
        return "#E6E6E6", "#666666"       # cinzento - sem alocação
    if pct > 100:
        return "#FFBEBE", "#7A1F1F"       # vermelho - sobre-alocado
    if pct == 100:
        return "#C8F0C8", "#1F5C1F"       # verde - 100%
    return "#FFF5C8", "#7A6A1F"           # amarelo - parcial


def _criar_barra_percentagem(pct: float) -> QWidget:
    fundo, texto = _cor_percentagem(pct)
    barra = QProgressBar()
    barra.setRange(0, 100)
    barra.setValue(min(int(pct), 100))
    barra.setFormat(f"{pct:.0f}%" if pct else "")
    barra.setTextVisible(pct > 0)
    barra.setFixedHeight(20)
    barra.setStyleSheet(f"""
        QProgressBar {{
            border: 1px solid #bbb;
            border-radius: 4px;
            background-color: {fundo};
            text-align: center;
            color: {texto};
            font-size: 10px;
        }}
        QProgressBar::chunk {{
            background-color: {'#E08A8A' if pct > 100 else '#8AC98A' if pct == 100 else '#E0CE7A' if pct > 0 else fundo};
            border-radius: 3px;
        }}
    """)
    return barra


class VistaCalendario(QWidget):
    """
    Calendário em formato de grelha: Cliente | Projeto | Tarefa | Deadline | <dias/meses...>
    com uma barra de percentagem de alocação por cada dia (ou mês, na vista anual).
    Navegação por período: Semanal, Mensal ou Anual.
    """

    def __init__(self):
        super().__init__()
        self.referencia = date.today()
        layout = QVBoxLayout(self)

        # ---------------- Barra de navegação de período ----------------
        nav = QHBoxLayout()
        nav.addWidget(QLabel("Período:"))
        self.periodo_combo = QComboBox()
        self.periodo_combo.addItems(PERIODOS)
        self.periodo_combo.setCurrentText("Mensal")
        nav.addWidget(self.periodo_combo)

        self.btn_anterior = QPushButton("◀ Anterior")
        self.btn_seguinte = QPushButton("Seguinte ▶")
        self.btn_hoje = QPushButton("Hoje")
        nav.addWidget(self.btn_anterior)
        nav.addWidget(self.btn_seguinte)
        nav.addWidget(self.btn_hoje)

        self.label_periodo = QLabel()
        self.label_periodo.setStyleSheet("font-weight: bold; font-size: 13px;")
        nav.addWidget(self.label_periodo)
        nav.addStretch()

        self.btn_exportar_excel = QPushButton("Exportar Excel")
        self.btn_exportar_pdf = QPushButton("Exportar PDF")
        nav.addWidget(self.btn_exportar_excel)
        nav.addWidget(self.btn_exportar_pdf)

        layout.addLayout(nav)

        # ---------------- Filtros ----------------
        filtros_box = QGroupBox("Filtros")
        filtros_form = QHBoxLayout()

        self.filtro_cliente = QComboBox()
        self.filtro_projeto = QComboBox()
        self.filtro_pessoa = QComboBox()
        self.filtro_estado = QComboBox()

        for label, combo in [
            ("Cliente", self.filtro_cliente), ("Projeto", self.filtro_projeto),
            ("Pessoa", self.filtro_pessoa), ("Estado", self.filtro_estado),
        ]:
            bloco = QVBoxLayout()
            bloco.addWidget(QLabel(label))
            bloco.addWidget(combo)
            filtros_form.addLayout(bloco)

        filtros_box.setLayout(filtros_form)
        layout.addWidget(filtros_box)

        # ---------------- Tabela ----------------
        self.tabela = QTableWidget()
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.tabela)

        # eventos
        self.periodo_combo.currentIndexChanged.connect(self._atualizar)
        self.btn_anterior.clicked.connect(self._ir_anterior)
        self.btn_seguinte.clicked.connect(self._ir_seguinte)
        self.btn_hoje.clicked.connect(self._ir_hoje)
        for combo in (self.filtro_cliente, self.filtro_projeto, self.filtro_pessoa, self.filtro_estado):
            combo.currentIndexChanged.connect(self._atualizar)
        self.btn_exportar_excel.clicked.connect(self._exportar_excel)
        self.btn_exportar_pdf.clicked.connect(self._exportar_pdf)

        self._popular_filtros()
        self._atualizar()

    # ------------------------------------------------------------------
    def _popular_filtros(self):
        session = get_session()
        try:
            def preencher(combo, itens, todos_label):
                atual = combo.currentData()
                combo.blockSignals(True)
                combo.clear()
                combo.addItem(todos_label, None)
                for item_id, item_label in itens:
                    combo.addItem(item_label, item_id)
                if atual is not None:
                    idx = combo.findData(atual)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                combo.blockSignals(False)

            preencher(self.filtro_cliente, [(c.id, c.nome) for c in session.query(Cliente).order_by(Cliente.nome)], "Todos")
            preencher(self.filtro_projeto, [(p.id, p.nome) for p in session.query(Projeto).order_by(Projeto.nome)], "Todos")
            preencher(self.filtro_pessoa, [(p.id, p.nome) for p in session.query(Pessoa).order_by(Pessoa.nome)], "Todas")
            preencher(self.filtro_estado, [(e, e) for e in ESTADOS_TAREFA], "Todos")
        finally:
            session.close()

    def refresh_filtros(self):
        """Chamar quando dados de outras vistas mudarem (ex: novo cliente/projeto)."""
        self._popular_filtros()
        self._atualizar()

    # ------------------------------------------------------------------
    def _ir_anterior(self):
        self.referencia = periodo_anterior(self.periodo_combo.currentText(), self.referencia)
        self._atualizar()

    def _ir_seguinte(self):
        self.referencia = periodo_seguinte(self.periodo_combo.currentText(), self.referencia)
        self._atualizar()

    def _ir_hoje(self):
        self.referencia = date.today()
        self._atualizar()

    # ------------------------------------------------------------------
    def _colunas_periodo(self):
        """
        Devolve lista de tuplos (rotulo_coluna, data_ini_coluna, data_fim_coluna).
        Para Semanal/Mensal cada coluna é um dia; para Anual cada coluna é um mês.
        """
        periodo = self.periodo_combo.currentText()
        if periodo == "Anual":
            colunas = []
            for mes, ini, fim in meses_do_ano(self.referencia.year):
                colunas.append((MESES_PT[mes - 1], ini, fim))
            return colunas

        colunas = []
        for dia in dias_do_periodo(periodo, self.referencia):
            rotulo = f"{DIAS_SEMANA_PT[dia.weekday()]}\n{dia.day}"
            colunas.append((rotulo, dia, dia))
        return colunas

    def _tarefas_filtradas(self, session, periodo_ini, periodo_fim):
        cliente_id = self.filtro_cliente.currentData()
        projeto_id = self.filtro_projeto.currentData()
        pessoa_id = self.filtro_pessoa.currentData()
        estado = self.filtro_estado.currentData()

        tarefas = session.query(Tarefa).all()
        resultado = []
        for t in tarefas:
            if not t.data_inicio or not t.data_fim:
                continue
            if t.data_fim < periodo_ini or t.data_inicio > periodo_fim:
                continue  # sem sobreposição com o período visível
            if estado and t.estado != estado:
                continue
            if projeto_id and t.projeto_id != projeto_id:
                continue
            if cliente_id and (not t.projeto or t.projeto.cliente_id != cliente_id):
                continue
            pessoas_da_tarefa = [a.pessoa for a in t.alocacoes if a.pessoa]
            if pessoa_id and not any(p.id == pessoa_id for p in pessoas_da_tarefa):
                continue
            resultado.append(t)

        resultado.sort(key=lambda t: (t.data_inicio, t.nome))
        return resultado

    def _percentagem_tarefa_no_intervalo(self, tarefa, ini, fim):
        """% total de alocação da tarefa, se ela estiver ativa em algum dia do intervalo [ini, fim]."""
        if not (tarefa.data_inicio <= fim and ini <= tarefa.data_fim):
            return 0.0
        pessoa_id = self.filtro_pessoa.currentData()
        total = 0.0
        for a in tarefa.alocacoes:
            if pessoa_id and a.pessoa_id != pessoa_id:
                continue
            total += float(a.percentagem or 0)
        return total

    # ------------------------------------------------------------------
    def _atualizar(self):
        periodo = self.periodo_combo.currentText()
        self.label_periodo.setText(descricao_periodo(periodo, self.referencia))
        periodo_ini, periodo_fim = intervalo_periodo(periodo, self.referencia)

        colunas = self._colunas_periodo()
        cabecalhos_base = ["Cliente", "Projeto", "Tarefa", "Deadline"]
        self.tabela.setColumnCount(len(cabecalhos_base) + len(colunas))
        self.tabela.setHorizontalHeaderLabels(cabecalhos_base + [c[0] for c in colunas])

        header = self.tabela.horizontalHeader()
        for i in range(len(cabecalhos_base)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        for i in range(len(cabecalhos_base), self.tabela.columnCount()):
            self.tabela.setColumnWidth(i, 60 if periodo != "Anual" else 55)

        session = get_session()
        try:
            tarefas = self._tarefas_filtradas(session, periodo_ini, periodo_fim)
            self.tabela.setRowCount(len(tarefas))

            for row, t in enumerate(tarefas):
                cliente_nome = t.projeto.cliente.nome if (t.projeto and t.projeto.cliente) else ""
                projeto_nome = t.projeto.nome if t.projeto else ""
                valores = [cliente_nome, projeto_nome, t.nome, str(t.data_fim) if t.data_fim else ""]
                for col, valor in enumerate(valores):
                    self.tabela.setItem(row, col, QTableWidgetItem(valor))

                for col_offset, (_rotulo, col_ini, col_fim) in enumerate(colunas):
                    pct = self._percentagem_tarefa_no_intervalo(t, col_ini, col_fim)
                    self.tabela.setCellWidget(row, len(cabecalhos_base) + col_offset, _criar_barra_percentagem(pct))
        finally:
            session.close()

    # ------------------------------------------------------------------
    def _tabela_para_exportacao(self):
        colunas_cab = []
        for c in range(self.tabela.columnCount()):
            texto = self.tabela.horizontalHeaderItem(c).text().replace("\n", " ")
            colunas_cab.append(texto)

        linhas = []
        for row in range(self.tabela.rowCount()):
            linha = []
            for col in range(4):
                item = self.tabela.item(row, col)
                linha.append(item.text() if item else "")
            for col in range(4, self.tabela.columnCount()):
                widget = self.tabela.cellWidget(row, col)
                linha.append(widget.format() if isinstance(widget, QProgressBar) and widget.text() else "")
            linhas.append(linha)
        return colunas_cab, linhas

    def _exportar_excel(self):
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar para Excel", "calendario.xlsx", "Ficheiros Excel (*.xlsx)")
        if not caminho:
            return
        colunas, linhas = self._tabela_para_exportacao()
        try:
            exportar_excel(caminho, "Calendário", colunas, linhas)
            QMessageBox.information(self, "Exportação concluída", f"Dados exportados para:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _exportar_pdf(self):
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar para PDF", "calendario.pdf", "Ficheiros PDF (*.pdf)")
        if not caminho:
            return
        colunas, linhas = self._tabela_para_exportacao()
        try:
            exportar_pdf(caminho, "Calendário", colunas, linhas)
            QMessageBox.information(self, "Exportação concluída", f"Dados exportados para:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
