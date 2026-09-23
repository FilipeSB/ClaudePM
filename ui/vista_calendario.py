from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QProgressBar, QFileDialog, QMessageBox
)

from database.db import get_session, listar_estados_tarefa
from database.models import Tarefa, Projeto, Cliente, Pessoa
from utils.periodos import (
    PERIODOS, intervalo_periodo, periodo_seguinte, periodo_anterior,
    descricao_periodo, dias_do_periodo, meses_do_ano,
)
from utils.exportacao import exportar_excel, exportar_pdf
from ui.filtro_multi_selecao import FiltroMultiSelecao

DIAS_SEMANA_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Paleta de cores distintas, uma por pessoa (repete em ciclo se houver muitas pessoas)
PALETA_PESSOAS = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC949", "#AF7AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
]


def _cor_pessoa(pessoa_id, mapa_cores):
    if pessoa_id not in mapa_cores:
        mapa_cores[pessoa_id] = PALETA_PESSOAS[len(mapa_cores) % len(PALETA_PESSOAS)]
    return mapa_cores[pessoa_id]


def _criar_barra_percentagem(pct: float, cor_hex: str) -> QWidget:
    barra = QProgressBar()
    barra.setRange(0, 100)
    barra.setValue(min(int(pct), 100) if pct else 0)
    barra.setFormat(f"{pct:.0f}%" if pct else "")
    barra.setTextVisible(pct > 0)
    barra.setFixedHeight(20)
    barra.setStyleSheet(f"""
        QProgressBar {{
            border: 1px solid #bbb;
            border-radius: 4px;
            background-color: #EDEDED;
            text-align: center;
            color: white;
            font-size: 10px;
            font-weight: bold;
        }}
        QProgressBar::chunk {{
            background-color: {cor_hex};
            border-radius: 3px;
        }}
    """)
    return barra


class VistaCalendario(QWidget):
    """
    Calendário em formato de grelha: Cliente | Projeto | Atividade | Pessoa |
    Percentagem de alocação | Estado da atividade | <dias/meses...>.
    Cada pessoa tem uma cor própria e consistente na barra dos dias.
    Navegação por período: Semanal, Mensal ou Anual. Filtro de estado permite
    seleção múltipla.
    """

    def __init__(self):
        super().__init__()
        self.referencia = date.today()
        self._cores_pessoas = {}
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

        for label, combo in [
            ("Cliente", self.filtro_cliente), ("Projeto", self.filtro_projeto),
            ("Pessoa", self.filtro_pessoa),
        ]:
            bloco = QVBoxLayout()
            bloco.addWidget(QLabel(label))
            bloco.addWidget(combo)
            filtros_form.addLayout(bloco)

        self.bloco_estado = QVBoxLayout()
        self.bloco_estado.addWidget(QLabel("Estado da Atividade"))
        self.filtro_estado = None  # construído em _reconstruir_filtro_estado()
        filtros_form.addLayout(self.bloco_estado)

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
        for combo in (self.filtro_cliente, self.filtro_projeto, self.filtro_pessoa):
            combo.currentIndexChanged.connect(self._atualizar)
        self.btn_exportar_excel.clicked.connect(self._exportar_excel)
        self.btn_exportar_pdf.clicked.connect(self._exportar_pdf)

        self._reconstruir_filtro_estado()
        self._popular_filtros()
        self._atualizar()

    # ------------------------------------------------------------------
    def _reconstruir_filtro_estado(self):
        """
        Reconstrói o filtro de Estado da Atividade a partir da lista atual
        de estados configurados (que pode mudar via menu Configurações),
        preservando a seleção anterior sempre que possível.
        """
        selecao_anterior = None
        valores_anteriores = set()
        if self.filtro_estado is not None:
            valores_anteriores = {v for v, _ in self.filtro_estado._checkboxes}
            selecao_anterior = set(self.filtro_estado.valores_selecionados())
            self.bloco_estado.removeWidget(self.filtro_estado)
            self.filtro_estado.deleteLater()

        session = get_session()
        try:
            estados = listar_estados_tarefa(session)
        finally:
            session.close()

        self.filtro_estado = FiltroMultiSelecao([(e, e) for e in estados], rotulo_todos="Todos os estados")
        if selecao_anterior is not None:
            for valor, cb in self.filtro_estado._checkboxes:
                # Estados que já existiam mantêm a seleção anterior; um
                # estado novo (recém-criado na gestão de estados) começa
                # sempre selecionado, para não ficar escondido por defeito.
                cb.setChecked(valor in selecao_anterior if valor in valores_anteriores else True)
        self.filtro_estado.alteracao.connect(self._atualizar)
        self.bloco_estado.addWidget(self.filtro_estado)

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
        finally:
            session.close()

    def refresh_filtros(self):
        """Chamar quando dados de outras vistas mudarem (ex: novo cliente/projeto)."""
        self._reconstruir_filtro_estado()
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

    def _linhas_filtradas(self, session, periodo_ini, periodo_fim):
        """
        Devolve lista de tuplos (tarefa, alocacao) -- uma linha por pessoa
        alocada a cada tarefa que cumpra os filtros e se sobreponha ao período.
        """
        cliente_id = self.filtro_cliente.currentData()
        projeto_id = self.filtro_projeto.currentData()
        pessoa_id = self.filtro_pessoa.currentData()
        estados_selecionados = self.filtro_estado.valores_selecionados()
        filtrar_estado = self.filtro_estado.filtro_ativo()

        tarefas = session.query(Tarefa).all()
        resultado = []
        for t in tarefas:
            if not t.data_inicio or not t.data_fim:
                continue
            if t.data_fim < periodo_ini or t.data_inicio > periodo_fim:
                continue  # sem sobreposição com o período visível
            if filtrar_estado and t.estado not in estados_selecionados:
                continue
            if projeto_id and t.projeto_id != projeto_id:
                continue
            if cliente_id and (not t.projeto or t.projeto.cliente_id != cliente_id):
                continue

            for a in t.alocacoes:
                if not a.pessoa:
                    continue
                if pessoa_id and a.pessoa_id != pessoa_id:
                    continue
                resultado.append((t, a))

        resultado.sort(key=lambda par: (par[0].data_inicio, par[0].nome, par[1].pessoa.nome))
        return resultado

    def _percentagem_no_dia(self, tarefa, alocacao, ini, fim):
        """% da alocação específica, se a tarefa estiver ativa em algum dia do intervalo [ini, fim]."""
        if not (tarefa.data_inicio <= fim and ini <= tarefa.data_fim):
            return 0.0
        return float(alocacao.percentagem or 0)

    # ------------------------------------------------------------------
    def _atualizar(self):
        periodo = self.periodo_combo.currentText()
        self.label_periodo.setText(descricao_periodo(periodo, self.referencia))
        periodo_ini, periodo_fim = intervalo_periodo(periodo, self.referencia)

        colunas_periodo = self._colunas_periodo()
        cabecalhos_base = ["Cliente", "Projeto", "Atividade", "Pessoa", "% Alocação", "Estado da Atividade"]
        self.tabela.setColumnCount(len(cabecalhos_base) + len(colunas_periodo))
        self.tabela.setHorizontalHeaderLabels(cabecalhos_base + [c[0] for c in colunas_periodo])

        header = self.tabela.horizontalHeader()
        for i in range(len(cabecalhos_base)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        for i in range(len(cabecalhos_base), self.tabela.columnCount()):
            self.tabela.setColumnWidth(i, 60 if periodo != "Anual" else 55)

        session = get_session()
        try:
            linhas_dados = self._linhas_filtradas(session, periodo_ini, periodo_fim)

            # Atribuir cor consistente a cada pessoa (ordenada por nome, para estabilidade visual)
            pessoas_ordenadas = sorted(
                {a.pessoa.id: a.pessoa.nome for _, a in linhas_dados}.items(), key=lambda x: x[1]
            )
            self._cores_pessoas = {}
            for pessoa_id, _nome in pessoas_ordenadas:
                _cor_pessoa(pessoa_id, self._cores_pessoas)

            self.tabela.setRowCount(len(linhas_dados))

            for row, (t, a) in enumerate(linhas_dados):
                cliente_nome = t.projeto.cliente.nome if (t.projeto and t.projeto.cliente) else ""
                projeto_nome = t.projeto.nome if t.projeto else ""
                pct_texto = f"{float(a.percentagem or 0):.0f}%"
                valores = [cliente_nome, projeto_nome, t.nome, a.pessoa.nome, pct_texto, t.estado]
                for col, valor in enumerate(valores):
                    self.tabela.setItem(row, col, QTableWidgetItem(valor))

                cor = _cor_pessoa(a.pessoa.id, self._cores_pessoas)
                for col_offset, (_rotulo, col_ini, col_fim) in enumerate(colunas_periodo):
                    pct = self._percentagem_no_dia(t, a, col_ini, col_fim)
                    self.tabela.setCellWidget(
                        row, len(cabecalhos_base) + col_offset,
                        _criar_barra_percentagem(pct, cor),
                    )
        finally:
            session.close()

    # ------------------------------------------------------------------
    def _tabela_para_exportacao(self):
        colunas_cab = []
        for c in range(self.tabela.columnCount()):
            texto = self.tabela.horizontalHeaderItem(c).text().replace("\n", " ")
            colunas_cab.append(texto)

        n_base = 6
        linhas = []
        for row in range(self.tabela.rowCount()):
            linha = []
            for col in range(n_base):
                item = self.tabela.item(row, col)
                linha.append(item.text() if item else "")
            for col in range(n_base, self.tabela.columnCount()):
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
