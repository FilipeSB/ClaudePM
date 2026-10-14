from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QFileDialog, QMessageBox, QMenu,
    QInputDialog, QStyledItemDelegate, QStyle, QAbstractItemView, QDialog, QDialogButtonBox,
    QDateEdit
)
from PySide6.QtGui import QColor, QPainter, QCursor
from PySide6.QtCore import Qt, QRect, QTimer, QDate
from sqlalchemy.orm import selectinload

from database.db import get_session, listar_estados_tarefa, conjunto_datas_feriados
from database.models import Tarefa, Projeto, Cliente, Pessoa, Alocacao, Feriado
from utils.periodos import (
    PERIODOS, intervalo_periodo, periodo_seguinte, periodo_anterior,
    descricao_periodo, dias_do_periodo, meses_do_ano,
)
from utils.exportacao import exportar_excel, exportar_pdf
from utils.calculos import percentagem_para_horas, horas_para_percentagem, e_dia_util
from utils.cores import cor_da_pessoa
from utils.formatacao import fmt_pct
from ui.filtro_multi_selecao import FiltroMultiSelecao
from ui.itens import ItemOrdenavel
from ui.barras import desenhar_barra
from ui.vista_tarefas import verificar_sobrealocacoes

DIAS_SEMANA_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Cores das colunas que não são dias úteis
COR_FIM_SEMANA = "#E3E3E3"
COR_FERIADO = "#F8D7DA"

# Colunas fixas (antes das colunas dos dias/meses)
CABECALHOS_BASE = [
    "Cliente", "Projeto", "Atividade", "Data de início", "Data fim",
    "Pessoa", "% Alocação", "Estado da Atividade",
]
C_CLIENTE, C_PROJETO, C_ATIVIDADE, C_INICIO, C_FIM, C_PESSOA, C_PCT, C_ESTADO = range(8)
N_BASE = len(CABECALHOS_BASE)

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
        desenhar_barra(painter, option.rect.adjusted(2, 3, -2, -3), float(pct), cor)


class VistaCalendario(QWidget):
    """
    Calendário em grelha: Cliente | Projeto | Atividade | Pessoa | % Alocação |
    Estado da Atividade | <dias/meses...>. Uma linha por pessoa alocada, cada
    pessoa com a sua cor. Todas as colunas são ordenáveis.

    Cliques:
      - Cliente / Projeto / Atividade: abre a janela de edição do registo.
      - Data de início / Data fim: abre um calendário para mudar a data da atividade.
      - Pessoa: mostra a lista de pessoas para trocar a pessoa alocada
        (e uma opção para editar a pessoa atual).
      - % Alocação: pergunta se o valor é em percentagem ou horas, e pede o valor.
      - Estado da Atividade: mostra a lista de estados para escolher.
    Os fins de semana e feriados aparecem a cinzento/rosa e não têm alocação.
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

        dica = QLabel("Clica num Cliente, Projeto ou Atividade para o editar; clica nas Datas, na Pessoa, "
                      "na % de Alocação ou no Estado para os alterar diretamente. "
                      "Cinzento = fim de semana; rosa = feriado (sem alocação).")
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
    def _percentagem_no_dia(tarefa, alocacao, ini, fim, feriados=None):
        """
        % da alocação na coluna [ini, fim]. A alocação só existe em dias úteis:
        numa coluna de um dia, fins de semana e feriados dão sempre 0.
        """
        if not (tarefa.data_inicio <= fim and ini <= tarefa.data_fim):
            return 0.0
        if ini == fim and not e_dia_util(ini, feriados):
            return 0.0
        return float(alocacao.percentagem or 0)

    # ------------------------------------------------------------------
    def _atualizar(self):
        periodo = self.periodo_combo.currentText()
        self.label_periodo.setText(descricao_periodo(periodo, self.referencia))
        periodo_ini, periodo_fim = intervalo_periodo(periodo, self.referencia)

        colunas_periodo = self._colunas_periodo()

        session = get_session()
        try:
            linhas_dados = self._linhas_filtradas(session, periodo_ini, periodo_fim)

            # Cada pessoa usa a cor escolhida no seu registo
            self._cores_pessoas = {
                a.pessoa.id: cor_da_pessoa(a.pessoa.cor, a.pessoa.id) for _, a in linhas_dados
            }
            feriados_desc = {f.data: (f.descricao or "Feriado") for f in session.query(Feriado).all()}
            feriados = set(feriados_desc)

            self.tabela.setSortingEnabled(False)
            self.tabela.clearContents()
            self.tabela.setColumnCount(N_BASE + len(colunas_periodo))
            # Itens de cabeçalho NOVOS em cada atualização. O Qt reaproveita os itens
            # existentes em setHorizontalHeaderLabels, por isso a cor de fim de semana
            # de uma vista (ex: a coluna 12 ser Domingo na vista semanal) ficava
            # "colada" a essa posição ao mudar de período (ex: em "Seg 7" ou em "Jun").
            for i, texto in enumerate(CABECALHOS_BASE + [c[0] for c in colunas_periodo]):
                self.tabela.setHorizontalHeaderItem(i, QTableWidgetItem(texto))
            # Cor de fundo (e dica) por coluna: só fins de semana e feriados
            cor_coluna = {}
            if periodo != "Anual":
                for off, (_rot, c_ini, _c_fim) in enumerate(colunas_periodo):
                    if c_ini in feriados:
                        cor_coluna[off] = (COR_FERIADO, f"Feriado: {feriados_desc[c_ini]}")
                    elif c_ini.weekday() >= 5:
                        cor_coluna[off] = (COR_FIM_SEMANA, "Fim de semana")
                for off, (cor, dica_col) in cor_coluna.items():
                    cab = self.tabela.horizontalHeaderItem(N_BASE + off)
                    cab.setBackground(QColor(cor))
                    cab.setForeground(QColor("#000000"))
                    cab.setToolTip(dica_col)
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
                    t.nome,
                    t.data_inicio.isoformat() if t.data_inicio else "",
                    t.data_fim.isoformat() if t.data_fim else "",
                    a.pessoa.nome, fmt_pct(a.percentagem), t.estado,
                ]
                for col, valor in enumerate(valores):
                    item = ItemOrdenavel(valor)
                    item.setData(R_TAREFA, int(t.id))
                    item.setData(R_ALOC, int(a.id))
                    item.setData(R_PESSOA, int(a.pessoa.id))
                    item.setData(R_PROJETO, int(t.projeto_id or 0))
                    item.setData(R_CLIENTE, int(cliente.id) if cliente else 0)
                    item.setData(R_PCT, float(a.percentagem or 0))
                    item.setToolTip("Clica para editar" if col in (C_CLIENTE, C_PROJETO, C_ATIVIDADE) else "Clica para alterar")
                    self.tabela.setItem(row, col, item)

                cor = self._cores_pessoas.get(a.pessoa.id) or cor_da_pessoa(a.pessoa.cor, a.pessoa.id)
                for off, (_rotulo, c_ini, c_fim) in enumerate(colunas_periodo):
                    pct = self._percentagem_no_dia(t, a, c_ini, c_fim, feriados)
                    item = ItemOrdenavel(fmt_pct(pct) if pct else "")
                    item.setData(R_BARRA_PCT, pct)
                    item.setData(R_BARRA_COR, cor)
                    if off in cor_coluna:
                        item.setBackground(QColor(cor_coluna[off][0]))
                        item.setToolTip(cor_coluna[off][1])
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
        def texto(c):
            it = self.tabela.item(row, c)
            return it.text() if it is not None else ""

        if col == C_CLIENTE:
            acao = ("cliente", item.data(R_CLIENTE) or 0)
        elif col == C_PROJETO:
            acao = ("projeto", item.data(R_PROJETO) or 0)
        elif col == C_ATIVIDADE:
            acao = ("tarefa", tarefa_id)
        elif col == C_INICIO:
            acao = ("data", tarefa_id, "inicio", texto(C_INICIO))
        elif col == C_FIM:
            acao = ("data", tarefa_id, "fim", texto(C_FIM))
        elif col == C_PESSOA:
            acao = ("pessoa", item.data(R_ALOC) or 0, item.data(R_PESSOA) or 0)
        elif col == C_PCT:
            acao = ("pct", item.data(R_ALOC) or 0, float(item.data(R_PCT) or 0))
        else:
            acao = ("estado", tarefa_id, texto(C_ESTADO))
        QTimer.singleShot(0, lambda a=acao: self._executar_acao(a))

    def _executar_acao(self, acao):
        try:
            tipo = acao[0]
            if tipo in ("cliente", "projeto", "tarefa"):
                registo_id = acao[1]
                editor = self._editores.get(tipo)
                if not registo_id or editor is None:
                    return
                editor(registo_id)
                self.refresh_filtros()
            elif tipo == "data":
                self._alterar_data(acao[1], acao[2], acao[3])
            elif tipo == "pessoa":
                self._alterar_pessoa(acao[1], acao[2])
            elif tipo == "estado":
                self._alterar_estado(acao[1], acao[2])
            elif tipo == "pct":
                self._alterar_percentagem(acao[1], acao[2])
        except Exception as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível concluir a ação:\n\n{exc}")

    # --- datas da atividade ---
    def _pedir_data(self, titulo, atual):
        """Abre um calendário para escolher uma data. Devolve a data ou None se cancelar."""
        dialog = QDialog(self)
        dialog.setWindowTitle(titulo)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"{titulo}:"))
        edit = QDateEdit(calendarPopup=True)
        edit.setDate(QDate(atual.year, atual.month, atual.day))
        layout.addWidget(edit)
        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(dialog.accept)
        botoes.rejected.connect(dialog.reject)
        layout.addWidget(botoes)
        if dialog.exec() != QDialog.Accepted:
            return None
        return edit.date().toPython()

    def _alterar_data(self, tarefa_id, campo, atual_iso):
        if not tarefa_id:
            return
        try:
            atual = date.fromisoformat(atual_iso)
        except (TypeError, ValueError):
            atual = date.today()
        titulo = "Data de início da atividade" if campo == "inicio" else "Data fim da atividade"
        nova = self._pedir_data(titulo, atual)
        if nova is None or nova == atual:
            return
        self._gravar_data(tarefa_id, campo, nova)

    def _gravar_data(self, tarefa_id, campo, nova_data, confirmar_sobrealocacao=True):
        session = get_session()
        try:
            tarefa = session.get(Tarefa, tarefa_id)
            if tarefa is None:
                return
            ini = nova_data if campo == "inicio" else tarefa.data_inicio
            fim = nova_data if campo == "fim" else tarefa.data_fim
            if ini and fim and fim < ini:
                QMessageBox.warning(
                    self, "Datas inválidas",
                    "A data de fim não pode ser anterior à data de início."
                )
                return
            if confirmar_sobrealocacao:
                # com o novo período, as pessoas alocadas podem ficar sobre-alocadas
                conflitos = verificar_sobrealocacoes(
                    session, tarefa.id, ini, fim,
                    [(a.pessoa_id, float(a.percentagem or 0)) for a in tarefa.alocacoes]
                )
                if conflitos:
                    resp = QMessageBox.warning(
                        self, "Sobre-alocação detetada",
                        "Com estas datas, as seguintes pessoas ficariam acima de 100% em período sobreposto:\n\n"
                        + "\n".join(conflitos) + "\n\nQueres gravar mesmo assim?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                    )
                    if resp != QMessageBox.Yes:
                        return
            if campo == "inicio":
                tarefa.data_inicio = nova_data
            else:
                tarefa.data_fim = nova_data
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        self._atualizar()

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

    # --- pessoa alocada ---
    def _escolher_pessoa(self, pessoas, atual_id):
        """pessoas: lista de (id, nome). Devolve o id escolhido, 'editar' ou None."""
        menu = QMenu(self)
        for pid, nome in pessoas:
            acao = menu.addAction(nome)
            acao.setData(pid)
            acao.setCheckable(True)
            acao.setChecked(pid == atual_id)
        menu.addSeparator()
        acao_editar = menu.addAction("Editar a pessoa atual...")
        acao_editar.setData("editar")
        escolhida = menu.exec(QCursor.pos())
        return escolhida.data() if escolhida is not None else None

    def _alterar_pessoa(self, aloc_id, pessoa_atual_id):
        if not aloc_id:
            return
        session = get_session()
        try:
            pessoas = [(p.id, p.nome) for p in session.query(Pessoa).filter_by(ativo=True).order_by(Pessoa.nome)]
            if pessoa_atual_id and pessoa_atual_id not in {pid for pid, _ in pessoas}:
                atual = session.get(Pessoa, pessoa_atual_id)
                if atual is not None:
                    pessoas.append((atual.id, f"{atual.nome} (inativo)"))
        finally:
            session.close()
        escolhida = self._escolher_pessoa(pessoas, pessoa_atual_id)
        if escolhida is None:
            return
        if escolhida == "editar":
            editor = self._editores.get("pessoa")
            if editor is not None and pessoa_atual_id:
                editor(pessoa_atual_id)
                self.refresh_filtros()
            return
        if escolhida == pessoa_atual_id:
            return
        self._gravar_pessoa(aloc_id, escolhida)

    def _gravar_pessoa(self, aloc_id, nova_pessoa_id, confirmar_sobrealocacao=True):
        session = get_session()
        try:
            aloc = session.get(Alocacao, aloc_id)
            if aloc is None:
                return
            tarefa = aloc.tarefa
            if any(o.pessoa_id == nova_pessoa_id for o in tarefa.alocacoes if o.id != aloc.id):
                QMessageBox.warning(
                    self, "Pessoa já alocada",
                    "Essa pessoa já está alocada a esta atividade. Edita a alocação existente em vez de duplicar."
                )
                return
            if confirmar_sobrealocacao:
                conflitos = verificar_sobrealocacoes(
                    session, tarefa.id, tarefa.data_inicio, tarefa.data_fim,
                    [(nova_pessoa_id, float(aloc.percentagem or 0))]
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
            aloc.pessoa_id = nova_pessoa_id
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        self._atualizar()

    # --- percentagem de alocação ---
    def _pedir_valor_alocacao(self, atual_pct):
        """
        Pergunta se o valor é em percentagem ou em horas (por dia útil de 8h) e
        pede o valor nessa unidade. Devolve (percentagem, tipo, horas) ou None.
        A percentagem é sempre o valor que fica guardado e visível nos registos.
        """
        unidade, ok = QInputDialog.getItem(
            self, "Alocação", "Introduzir o valor em:",
            ["Percentagem (%)", "Horas por dia útil (h)"], 0, False
        )
        if not ok:
            return None
        if unidade.startswith("Horas"):
            valor, ok = QInputDialog.getDouble(
                self, "Alocação em horas", "Horas por dia útil (8 h = 100%):",
                percentagem_para_horas(atual_pct), 0.0, 8.0, 1
            )
            if not ok:
                return None
            return horas_para_percentagem(valor), "horas", valor
        valor, ok = QInputDialog.getDouble(
            self, "Alocação em percentagem", "Nova percentagem (%):", float(atual_pct), 0.0, 100.0, 1
        )
        if not ok:
            return None
        return valor, "percentagem", None

    def _alterar_percentagem(self, aloc_id, atual):
        if not aloc_id:
            return
        resultado = self._pedir_valor_alocacao(atual)
        if resultado is None:
            return
        novo, tipo, horas = resultado
        if abs(novo - atual) < 1e-9:
            return
        self._gravar_percentagem(aloc_id, novo, tipo=tipo, horas=horas)

    def _gravar_percentagem(self, aloc_id, novo, confirmar_sobrealocacao=True, tipo="percentagem", horas=None):
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
            aloc.tipo = tipo
            aloc.horas = horas
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
