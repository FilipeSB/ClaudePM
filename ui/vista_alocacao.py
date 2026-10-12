from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QFileDialog, QMessageBox,
    QStyledItemDelegate, QStyle
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtCore import Qt, QRect

from database.db import get_session, listar_estados_tarefa
from database.models import Pessoa, Tarefa, Projeto, Cliente
from utils.periodos import PERIODOS, intervalo_periodo, periodo_seguinte, periodo_anterior, descricao_periodo
from utils.exportacao import exportar_excel, exportar_pdf
from ui.filtro_multi_selecao import FiltroMultiSelecao
from ui.itens import ItemOrdenavel
from utils.formatacao import fmt_pct
from utils.cores import cor_da_pessoa
from ui.barras import desenhar_barra


R_PCT = Qt.UserRole + 20
R_COR = Qt.UserRole + 21


class BarraAlocacaoDelegate(QStyledItemDelegate):
    """
    Desenha, na coluna "% Alocada no período", uma barra cujo comprimento é
    proporcional à percentagem (100% = célula toda) e que usa a cor da pessoa.
    Acima de 100% (sobre-alocação) a barra fica cheia com contorno vermelho.
    """

    def paint(self, painter, option, index):
        pct = index.data(R_PCT)
        if pct is None:
            super().paint(painter, option, index)
            return
        cor = index.data(R_COR) or "#4E79A7"
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        desenhar_barra(painter, option.rect.adjusted(3, 4, -3, -4), float(pct), cor)


def _sobrepoe(inicio1, fim1, inicio2, fim2):
    if not all([inicio1, fim1, inicio2, fim2]):
        return False
    return inicio1 <= fim2 and inicio2 <= fim1


class VistaAlocacao(QWidget):
    """
    Percentagem de alocação de cada pessoa, agregada num período (Semanal /
    Mensal / Anual, navegável), com filtros adicionais por Cliente, Projeto,
    Tarefa e Estado da Tarefa (seleção múltipla). Assinala visualmente
    sobre-alocação (>100%).
    """

    def __init__(self):
        super().__init__()
        self.referencia = date.today()
        self.filtro_estado = None  # construído em _reconstruir_filtro_estado()
        layout = QVBoxLayout(self)

        # ---------------- Navegação de período ----------------
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

        btn_excel = QPushButton("Exportar Excel")
        btn_pdf = QPushButton("Exportar PDF")
        nav.addWidget(btn_excel)
        nav.addWidget(btn_pdf)
        layout.addLayout(nav)

        # ---------------- Filtros ----------------
        filtros_box = QGroupBox("Filtros")
        filtros_layout = QHBoxLayout()

        self.filtro_cliente = QComboBox()
        self.filtro_projeto = QComboBox()
        self.filtro_tarefa = QComboBox()

        for label, combo in [
            ("Cliente", self.filtro_cliente), ("Projeto", self.filtro_projeto),
            ("Tarefa", self.filtro_tarefa),
        ]:
            bloco = QVBoxLayout()
            bloco.addWidget(QLabel(label))
            bloco.addWidget(combo)
            filtros_layout.addLayout(bloco)

        self.bloco_estado = QVBoxLayout()
        self.bloco_estado.addWidget(QLabel("Estado da Tarefa"))
        filtros_layout.addLayout(self.bloco_estado)

        filtros_box.setLayout(filtros_layout)
        layout.addWidget(filtros_box)

        # ---------------- Tabela ----------------
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(5)
        self.tabela.setHorizontalHeaderLabels(
            ["Pessoa", "Equipa", "Perfil", "% Alocada no período", "Detalhe das Tarefas"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._delegate_barra = BarraAlocacaoDelegate(self.tabela)
        self.tabela.setItemDelegateForColumn(3, self._delegate_barra)
        self.tabela.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self.tabela.setSortingEnabled(True)
        layout.addWidget(self.tabela)

        # eventos
        self.periodo_combo.currentIndexChanged.connect(self.refresh)
        self.btn_anterior.clicked.connect(self._ir_anterior)
        self.btn_seguinte.clicked.connect(self._ir_seguinte)
        self.btn_hoje.clicked.connect(self._ir_hoje)
        self.filtro_cliente.currentIndexChanged.connect(self._ao_mudar_cliente)
        self.filtro_projeto.currentIndexChanged.connect(self._ao_mudar_projeto)
        self.filtro_tarefa.currentIndexChanged.connect(self.refresh)
        btn_excel.clicked.connect(self._exportar_excel)
        btn_pdf.clicked.connect(self._exportar_pdf)

        self._reconstruir_filtro_estado()
        self._popular_filtros()
        self.refresh()

    # ------------------------------------------------------------------
    def _reconstruir_filtro_estado(self):
        """Reconstrói o filtro de Estado da Tarefa a partir da lista atual de estados configurados."""
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
                cb.setChecked(valor in selecao_anterior if valor in valores_anteriores else True)
        self.filtro_estado.alteracao.connect(self.refresh)
        self.bloco_estado.addWidget(self.filtro_estado)

    def _popular_filtros(self, manter_projeto=False, manter_tarefa=False):
        session = get_session()
        try:
            def preencher(combo, itens, todos_label, manter):
                atual = combo.currentData() if manter else None
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

            # O cliente mantém sempre a sua própria seleção ao recarregar
            # (só muda por ação direta do utilizador nesse combo).
            preencher(self.filtro_cliente, [(c.id, c.nome) for c in session.query(Cliente).order_by(Cliente.nome)], "Todos", manter=True)

            query_projetos = session.query(Projeto)
            cliente_id = self.filtro_cliente.currentData()
            if cliente_id:
                query_projetos = query_projetos.filter_by(cliente_id=cliente_id)
            preencher(self.filtro_projeto, [(p.id, p.nome) for p in query_projetos.order_by(Projeto.nome)], "Todos", manter=manter_projeto)

            query_tarefas = session.query(Tarefa)
            projeto_id = self.filtro_projeto.currentData()
            if projeto_id:
                query_tarefas = query_tarefas.filter_by(projeto_id=projeto_id)
            elif cliente_id:
                query_tarefas = query_tarefas.join(Projeto).filter(Projeto.cliente_id == cliente_id)
            preencher(self.filtro_tarefa, [(t.id, t.nome) for t in query_tarefas.order_by(Tarefa.nome)], "Todas", manter=manter_tarefa)
        finally:
            session.close()

    def _ao_mudar_cliente(self):
        # cliente mudou: reiniciar projeto e tarefa (podem já não fazer sentido)
        self._popular_filtros(manter_projeto=False, manter_tarefa=False)
        self.refresh()

    def _ao_mudar_projeto(self):
        # projeto mudou: manter cliente, reiniciar tarefa
        self._popular_filtros(manter_projeto=True, manter_tarefa=False)
        self.refresh()

    def refresh_filtros(self):
        self._reconstruir_filtro_estado()
        self._popular_filtros(manter_projeto=True, manter_tarefa=True)
        self.refresh()

    # ------------------------------------------------------------------
    def _ir_anterior(self):
        self.referencia = periodo_anterior(self.periodo_combo.currentText(), self.referencia)
        self.refresh()

    def _ir_seguinte(self):
        self.referencia = periodo_seguinte(self.periodo_combo.currentText(), self.referencia)
        self.refresh()

    def _ir_hoje(self):
        self.referencia = date.today()
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self):
        periodo = self.periodo_combo.currentText()
        self.label_periodo.setText(descricao_periodo(periodo, self.referencia))
        periodo_ini, periodo_fim = intervalo_periodo(periodo, self.referencia)

        cliente_id = self.filtro_cliente.currentData()
        projeto_id = self.filtro_projeto.currentData()
        tarefa_id = self.filtro_tarefa.currentData()
        estados_selecionados = self.filtro_estado.valores_selecionados()
        filtrar_estado = self.filtro_estado.filtro_ativo()

        session = get_session()
        try:
            pessoas = session.query(Pessoa).filter_by(ativo=True).order_by(Pessoa.nome).all()
            self.tabela.setSortingEnabled(False)
            self.tabela.setRowCount(len(pessoas))

            for row, pessoa in enumerate(pessoas):
                total = 0.0
                detalhe = []
                for a in pessoa.alocacoes:
                    t = a.tarefa
                    if not t or not t.data_inicio or not t.data_fim:
                        continue
                    if not _sobrepoe(periodo_ini, periodo_fim, t.data_inicio, t.data_fim):
                        continue
                    if filtrar_estado and t.estado not in estados_selecionados:
                        continue
                    if tarefa_id and t.id != tarefa_id:
                        continue
                    if projeto_id and t.projeto_id != projeto_id:
                        continue
                    if cliente_id and (not t.projeto or t.projeto.cliente_id != cliente_id):
                        continue

                    total += float(a.percentagem or 0)
                    detalhe.append(f"{t.nome} ({fmt_pct(a.percentagem)})")

                self.tabela.setItem(row, 0, ItemOrdenavel(pessoa.nome))
                self.tabela.setItem(row, 1, ItemOrdenavel(pessoa.equipa.nome if pessoa.equipa else ""))
                self.tabela.setItem(row, 2, ItemOrdenavel(pessoa.perfil.codigo if pessoa.perfil else ""))

                item_pct = ItemOrdenavel(fmt_pct(total))
                item_pct.setData(R_PCT, total)
                item_pct.setData(R_COR, cor_da_pessoa(pessoa.cor, pessoa.id))
                self.tabela.setItem(row, 3, item_pct)
                self.tabela.setItem(row, 4, ItemOrdenavel(", ".join(detalhe)))
            self.tabela.setSortingEnabled(True)
        finally:
            session.close()

    # ------------------------------------------------------------------
    def _colunas(self):
        return [self.tabela.horizontalHeaderItem(c).text() for c in range(self.tabela.columnCount())]

    def _linhas(self):
        linhas = []
        for row in range(self.tabela.rowCount()):
            linha = []
            for col in range(self.tabela.columnCount()):
                item = self.tabela.item(row, col)
                linha.append(item.text() if item else "")
            linhas.append(linha)
        return linhas

    def _exportar_excel(self):
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar para Excel", "alocacao.xlsx", "Ficheiros Excel (*.xlsx)")
        if not caminho:
            return
        try:
            exportar_excel(caminho, "Alocação", self._colunas(), self._linhas())
            QMessageBox.information(self, "Exportação concluída", f"Dados exportados para:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _exportar_pdf(self):
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar para PDF", "alocacao.pdf", "Ficheiros PDF (*.pdf)")
        if not caminho:
            return
        try:
            exportar_pdf(caminho, "Alocação", self._colunas(), self._linhas())
            QMessageBox.information(self, "Exportação concluída", f"Dados exportados para:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
