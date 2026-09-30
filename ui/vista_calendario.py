from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton,
    QTableWidget, QHeaderView, QGroupBox, QFileDialog, QMessageBox, QMenu,
    QInputDialog, QStyledItemDelegate, QStyle, QAbstractItemView
)
from PySide6.QtGui import QColor, QPainter, QCursor
from PySide6.QtCore import Qt, QRect, QTimer
from sqlalchemy.orm import selectinload

from database.db import get_session, listar_estados_tarefa
from database.models import Tarefa, Projeto, Cliente, Pessoa, Alocacao
from utils.periodos import (
    PERIODOS, intervalo_periodo, periodo_seguinte, periodo_anterior,
    descricao_periodo, dias_do_periodo, meses_do_ano,
)
from utils.exportacao import exportar_excel, exportar_pdf
from utils.calculos import percentagem_para_horas
from utils.formatacao import fmt_pct
from ui.filtro_multi_selecao import FiltroMultiSelecao
from ui.itens import ItemOrdenavel
from ui.vista_tarefas import verificar_sobrealocacoes

DIAS_SEMANA_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Paleta de cores distintas, uma por pessoa (repete em ciclo se houver muitas pessoas)
PALETA_PESSOAS = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC949", "#AF7AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
]

N_BASE = 6  # Cliente, Projeto, Atividade, Pessoa, % Alocação, Estado da Atividade

# Dados guardados em cada linha (apenas inteiros/números simples)
R_TAREFA = Qt.UserRole
R_ALOC = Qt.UserRole + 1
R_PESSOA = Qt.UserRole + 2
R_PROJETO = Qt.UserRole + 3
R_CLIENTE = Qt.UserRole + 4
R_PCT = Qt.UserRole + 5
# Dados das células dos dias
R_BARRA_PCT = Qt.UserRole + 10
R_BARRA_COR = Qt.UserRole + 11


class BarraPercentagemDelegate(QStyledItemDelegate):
    """
    Desenha a barra de percentagem das células dos dias. Em vez de um widget
    por célula (centenas ou milhares de widgets a criar/destruir em cada
    atualização), a barra é apenas desenhada -- mais leve e mais estável.
    """

    def paint(self, painter, option, index):
        pct = index.data(R_BARRA_PCT) if index.column() >= N_BASE else None
        if not pct:
            super().paint(painter, option, index)
            return
        cor = index.data(R_BARRA_COR) or "#4E79A7"
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        rect = option.rect.adjusted(2, 3, -2, -3)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#bbbbbb"))
        painter.setBrush(QColor("#EDEDED"))
        painter.drawRoundedRect(rect, 3, 3)
        largura = int(rect.width() * min(float(pct), 100.0) / 100.0)
        if largura > 0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(cor))
            painter.drawRoundedRect(QRect(rect.x(), rect.y(), largura, rect.height()), 3, 3)
        painter.setPen(QColor("#111111"))
        painter.drawText(rect, Qt.AlignCenter, fmt_pct(pct))
        painter.restore()


class VistaCalendario(QWidget):
    """
    Calendário em grelha: Cliente | Projeto | Atividade | Pessoa | % Alocação |
    Estado da Atividade | <dias/meses...>. Uma linha por pessoa alocada, cada
    pessoa com a sua cor. Todas as colunas são ordenáveis.

    Cliques:
      - Cliente / Projeto / Atividade / Pessoa: abre a janela de edição do registo.
      - % Alocação: pede o novo valor.
      - Estado da Atividade: mostra a lista de estados para escolher.
    """

    def __init__(self):
        super().__init__()
        self.referencia = date.today()
        self._cores_pessoas = {}
        self._editores = {}
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

        dica = QLabel("Clica num Cliente, Projeto, Atividade ou Pessoa para o editar; "
                      "clica na % de Alocação ou no Estado para os alterar diretamente.")
        dica.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(dica)

        # ---------------- Tabela ----------------
        self.tabela = QTableWidget()
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SingleSelection)
        self._delegate = BarraPercentagemDelegate(self.tabela)
        self.tabela.setItemDelegate(self._delegate)
        self.tabela.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self.tabela.setSortingEnabled(True)
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
        self.tabela.cellClicked.connect(self._ao_clicar)

        self._reconstruir_filtro_estado()
        self._popular_filtros()
        self._atualizar()

    def definir_editores(self, editores: dict):
        """
        Liga o calendário às janelas de edição das outras vistas:
        {'cliente': f, 'projeto': f, 'tarefa': f, 'pessoa': f}, onde cada f(id)
        abre a janela de edição desse registo.
        """
        self._editores = dict(editores)

    # ------------------------------------------------------------------
    def _reconstruir_filtro_estado(self):
        """Reconstrói o filtro de Estado da Atividade a partir dos estados configurados."""
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
        self.filtro_estado.alteracao.connect(self._atualizar)
        self.bloco_estado.addWidget(self.filtro_estado)

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
        """Chamar quando dados de outras vistas mudarem."""
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
        """Lista de (rotulo, data_ini, data_fim): dias (Semanal/Mensal) ou meses (Anual)."""
        periodo = self.periodo_combo.currentText()
        if periodo == "Anual":
            return [(MESES_PT[mes - 1], ini, fim) for mes, ini, fim in meses_do_ano(self.referencia.year)]
        colunas = []
        for dia in dias_do_periodo(periodo, self.referencia):
            colunas.append((f"{DIAS_SEMANA_PT[dia.weekday()]}\n{dia.day}", dia, dia))
        return colunas

    def _linhas_filtradas(self, session, periodo_ini, periodo_fim):
        """Lista de (tarefa, alocacao): uma linha por pessoa alocada a cada atividade que cumpra os filtros."""
        cliente_id = self.filtro_cliente.currentData()
        projeto_id = self.filtro_projeto.currentData()
        pessoa_id = self.filtro_pessoa.currentData()
        estados_selecionados = self.filtro_estado.valores_selecionados()
        filtrar_estado = self.filtro_estado.filtro_ativo()

        tarefas = (
            session.query(Tarefa)
            .options(
                selectinload(Tarefa.alocacoes).selectinload(Alocacao.pessoa),
                selectinload(Tarefa.projeto).selectinload(Projeto.cliente),
            )
            .all()
        )
        resultado = []
        for t in tarefas:
            if not t.data_inicio or not t.data_fim:
                continue
            if t.data_fim < periodo_ini or t.data_inicio > periodo_fim:
                continue
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

    @staticmethod
    def _percentagem_no_dia(tarefa, alocacao, ini, fim):
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

        session = get_session()
        try:
            linhas_dados = self._linhas_filtradas(session, periodo_ini, periodo_fim)

            self._cores_pessoas = {}
            for pessoa_id, _nome in sorted({a.pessoa.id: a.pessoa.nome for _, a in linhas_dados}.items(), key=lambda x: x[1]):
                self._cores_pessoas[pessoa_id] = PALETA_PESSOAS[len(self._cores_pessoas) % len(PALETA_PESSOAS)]

            self.tabela.setSortingEnabled(False)
            self.tabela.clearContents()
            self.tabela.setColumnCount(N_BASE + len(colunas_periodo))
            self.tabela.setHorizontalHeaderLabels(cabecalhos_base + [c[0] for c in colunas_periodo])
            header = self.tabela.horizontalHeader()
            for i in range(N_BASE):
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            for i in range(N_BASE, self.tabela.columnCount()):
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                self.tabela.setColumnWidth(i, 62)
            self.tabela.setRowCount(len(linhas_dados))

            for row, (t, a) in enumerate(linhas_dados):
                cliente = t.projeto.cliente if (t.projeto and t.projeto.cliente) else None
                valores = [
                    cliente.nome if cliente else "",
                    t.projeto.nome if t.projeto else "",
                    t.nome, a.pessoa.nome, fmt_pct(a.percentagem), t.estado,
                ]
                for col, valor in enumerate(valores):
                    item = ItemOrdenavel(valor)
                    item.setData(R_TAREFA, int(t.id))
                    item.setData(R_ALOC, int(a.id))
                    item.setData(R_PESSOA, int(a.pessoa.id))
                    item.setData(R_PROJETO, int(t.projeto_id or 0))
                    item.setData(R_CLIENTE, int(cliente.id) if cliente else 0)
                    item.setData(R_PCT, float(a.percentagem or 0))
                    item.setToolTip("Clica para editar" if col != 4 and col != 5 else "Clica para alterar")
                    self.tabela.setItem(row, col, item)

                cor = self._cores_pessoas.get(a.pessoa.id, PALETA_PESSOAS[0])
                for off, (_rotulo, c_ini, c_fim) in enumerate(colunas_periodo):
                    pct = self._percentagem_no_dia(t, a, c_ini, c_fim)
                    item = ItemOrdenavel(fmt_pct(pct) if pct else "")
                    item.setData(R_BARRA_PCT, pct)
                    item.setData(R_BARRA_COR, cor)
                    self.tabela.setItem(row, N_BASE + off, item)
            self.tabela.setSortingEnabled(True)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Cliques
    # ------------------------------------------------------------------
    def _ao_clicar(self, row, col):
        """
        Só recolhe os dados do clique e adia a ação para a iteração seguinte do
        event loop: as ações abrem janelas e atualizam a tabela, e modificar a
        tabela de dentro do seu próprio sinal de clique é instável em Qt.
        """
        if col >= N_BASE:
            return
        item = self.tabela.item(row, 0)
        if item is None:
            return
        tarefa_id = item.data(R_TAREFA) or 0
        if col == 0:
            acao = ("cliente", item.data(R_CLIENTE) or 0)
        elif col == 1:
            acao = ("projeto", item.data(R_PROJETO) or 0)
        elif col == 2:
            acao = ("tarefa", tarefa_id)
        elif col == 3:
            acao = ("pessoa", item.data(R_PESSOA) or 0)
        elif col == 4:
            acao = ("pct", item.data(R_ALOC) or 0, float(item.data(R_PCT) or 0))
        else:
            estado_item = self.tabela.item(row, 5)
            acao = ("estado", tarefa_id, estado_item.text() if estado_item else "")
        QTimer.singleShot(0, lambda a=acao: self._executar_acao(a))

    def _executar_acao(self, acao):
        try:
            tipo = acao[0]
            if tipo in ("cliente", "projeto", "tarefa", "pessoa"):
                registo_id = acao[1]
                editor = self._editores.get(tipo)
                if not registo_id or editor is None:
                    return
                editor(registo_id)
                self.refresh_filtros()
            elif tipo == "estado":
                self._alterar_estado(acao[1], acao[2])
            elif tipo == "pct":
                self._alterar_percentagem(acao[1], acao[2])
        except Exception as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível concluir a ação:\n\n{exc}")

    # --- estado da atividade ---
    def _escolher_estado(self, estados, atual):
        menu = QMenu(self)
        for e in estados:
            acao = menu.addAction(e)
            acao.setData(e)
            acao.setCheckable(True)
            acao.setChecked(e == atual)
        escolhida = menu.exec(QCursor.pos())
        return escolhida.data() if escolhida is not None else None

    def _alterar_estado(self, tarefa_id, atual):
        if not tarefa_id:
            return
        session = get_session()
        try:
            estados = listar_estados_tarefa(session)
        finally:
            session.close()
        if atual and atual not in estados:
            estados = estados + [atual]
        novo = self._escolher_estado(estados, atual)
        if novo is None or novo == atual:
            return
        self._gravar_estado(tarefa_id, novo)

    def _gravar_estado(self, tarefa_id, novo_estado):
        session = get_session()
        try:
            tarefa = session.get(Tarefa, tarefa_id)
            if tarefa is not None:
                tarefa.estado = novo_estado
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        self._atualizar()

    # --- percentagem de alocação ---
    def _pedir_percentagem(self, atual):
        valor, ok = QInputDialog.getDouble(
            self, "Percentagem de alocação", "Nova percentagem (%):", float(atual), 0.0, 100.0, 1
        )
        return valor if ok else None

    def _alterar_percentagem(self, aloc_id, atual):
        if not aloc_id:
            return
        novo = self._pedir_percentagem(atual)
        if novo is None or abs(novo - atual) < 1e-9:
            return
        self._gravar_percentagem(aloc_id, novo)

    def _gravar_percentagem(self, aloc_id, novo, confirmar_sobrealocacao=True):
        session = get_session()
        try:
            aloc = session.get(Alocacao, aloc_id)
            if aloc is None:
                return
            tarefa = aloc.tarefa
            if confirmar_sobrealocacao:
                conflitos = verificar_sobrealocacoes(
                    session, tarefa.id, tarefa.data_inicio, tarefa.data_fim, [(aloc.pessoa_id, novo)]
                )
                if conflitos:
                    resp = QMessageBox.warning(
                        self, "Sobre-alocação detetada",
                        "Esta pessoa ficaria alocada acima de 100% em período sobreposto:\n\n"
                        + "\n".join(conflitos) + "\n\nQueres gravar mesmo assim?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                    )
                    if resp != QMessageBox.Yes:
                        return
            aloc.percentagem = novo
            if aloc.tipo == "horas":
                aloc.horas = percentagem_para_horas(novo, aloc.categoria or "8h_uteis")
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        self._atualizar()

    # ------------------------------------------------------------------
    def _tabela_para_exportacao(self):
        colunas_cab = []
        for c in range(self.tabela.columnCount()):
            cab = self.tabela.horizontalHeaderItem(c)
            colunas_cab.append(cab.text().replace("\n", " ") if cab else "")
        linhas = []
        for row in range(self.tabela.rowCount()):
            linha = []
            for col in range(self.tabela.columnCount()):
                item = self.tabela.item(row, col)
                linha.append(item.text() if item else "")
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
