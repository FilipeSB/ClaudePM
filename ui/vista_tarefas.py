from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QDateEdit, QDialogButtonBox,
    QVBoxLayout, QHBoxLayout, QMessageBox, QPushButton, QDoubleSpinBox,
    QWidget, QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import QTimer
from sqlalchemy.orm import selectinload
from database.db import get_session, listar_estados_tarefa
from database.models import Tarefa, Projeto, Cliente, Pessoa, Alocacao
from ui.base_crud import BaseCrudWidget
from ui.vista_projetos import qdate_to_pydate, pydate_to_qdate
from utils.calculos import horas_para_percentagem, percentagem_para_horas
from utils.formatacao import fmt_pct


def sobreposicao_datas(inicio1, fim1, inicio2, fim2):
    if not all([inicio1, fim1, inicio2, fim2]):
        return False
    return inicio1 <= fim2 and inicio2 <= fim1


def verificar_sobrealocacoes(session, tarefa_id, data_inicio, data_fim, alocacoes_novas):
    """
    Para cada (pessoa_id, percentagem, ...) da atividade em edição, soma as
    percentagens de OUTRAS atividades dessa pessoa com período sobreposto e
    verifica se, somado à nova percentagem, ultrapassa 100%.
    Retorna lista de textos com os conflitos (vazia se estiver tudo bem).
    """
    conflitos = []
    for pessoa_id, pct_nova, *_ in alocacoes_novas:
        pessoa = session.get(Pessoa, pessoa_id)
        if not pessoa:
            continue

        total_outras = 0.0
        for a in pessoa.alocacoes:
            if a.tarefa_id == tarefa_id:
                continue  # ignora alocações da própria atividade (serão substituídas)
            t = a.tarefa
            if not t:
                continue
            if sobreposicao_datas(data_inicio, data_fim, t.data_inicio, t.data_fim):
                total_outras += float(a.percentagem or 0)

        total = total_outras + pct_nova
        if total > 100:
            conflitos.append(
                f"{pessoa.nome}: {fmt_pct(total)} no total ({fmt_pct(total_outras)} noutras atividades "
                f"sobrepostas + {fmt_pct(pct_nova)} nesta atividade)"
            )
    return conflitos


class AlocacaoRowWidget(QWidget):
    """
    Uma linha de alocação: pessoa + tipo (%/horas) + valor + remover.
    A alocação é sempre relativa a um dia útil de 8 horas (sem outras
    categorias), por isso converter entre horas e percentagem é direto.
    """

    def __init__(self, pessoas, pessoa_id=None, percentagem=0, tipo="percentagem",
                 horas=None, ao_remover=None):
        """pessoas: lista de tuplos (id, texto_a_mostrar)."""
        super().__init__()
        self._ao_remover = ao_remover

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.pessoa_combo = QComboBox()
        for pid, texto in pessoas:
            self.pessoa_combo.addItem(texto, pid)
        if pessoa_id:
            idx = self.pessoa_combo.findData(pessoa_id)
            if idx >= 0:
                self.pessoa_combo.setCurrentIndex(idx)

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItem("Percentagem", "percentagem")
        self.tipo_combo.addItem("Horas (dia útil)", "horas")
        idx_tipo = self.tipo_combo.findData(tipo)
        if idx_tipo >= 0:
            self.tipo_combo.setCurrentIndex(idx_tipo)

        self.valor_spin = QDoubleSpinBox()
        self.valor_spin.setDecimals(1)
        self._configurar_valor_spin(percentagem, horas, tipo)

        self.btn_remover = QPushButton("✕")
        self.btn_remover.setFixedWidth(28)
        self.btn_remover.setToolTip("Remover esta pessoa da atividade")
        self.btn_remover.clicked.connect(self._remover)

        layout.addWidget(self.pessoa_combo, 3)
        layout.addWidget(self.tipo_combo, 2)
        layout.addWidget(self.valor_spin, 2)
        layout.addWidget(self.btn_remover)

        self.tipo_combo.currentIndexChanged.connect(self._ao_mudar_tipo)

    def _configurar_valor_spin(self, percentagem, horas, tipo):
        if tipo == "horas":
            self.valor_spin.setRange(0, 8)
            self.valor_spin.setSuffix(" h")
            self.valor_spin.setValue(float(horas) if horas is not None else percentagem_para_horas(percentagem))
        else:
            self.valor_spin.setRange(0, 100)
            self.valor_spin.setSuffix(" %")
            self.valor_spin.setValue(float(percentagem or 0))

    def _ao_mudar_tipo(self):
        """Ao trocar de unidade, o valor é convertido de imediato (não fica a zeros)."""
        tipo_novo = self.tipo_combo.currentData()
        valor_atual = self.valor_spin.value()
        if tipo_novo == "horas":
            novo_valor = percentagem_para_horas(valor_atual)  # vinha de percentagem
            self.valor_spin.setRange(0, 8)
            self.valor_spin.setSuffix(" h")
        else:
            novo_valor = horas_para_percentagem(valor_atual)  # vinha de horas
            self.valor_spin.setRange(0, 100)
            self.valor_spin.setSuffix(" %")
        self.valor_spin.setValue(novo_valor)

    def _remover(self):
        # Remoção diferida: destruir este widget de dentro do handler de
        # clique do seu próprio botão é instável em Qt (causa de fechos
        # inesperados). Diferir para a iteração seguinte do event loop evita-o.
        QTimer.singleShot(0, self._remover_efetivo)

    def _remover_efetivo(self):
        if self._ao_remover:
            self._ao_remover(self)
        pai = self.parentWidget()
        if pai is not None and pai.layout() is not None:
            pai.layout().removeWidget(self)
        self.hide()
        self.deleteLater()

    def dados(self):
        """Retorna (pessoa_id, percentagem, tipo, horas)."""
        pessoa_id = self.pessoa_combo.currentData()
        tipo = self.tipo_combo.currentData()
        valor = self.valor_spin.value()
        if tipo == "horas":
            horas = valor
            percentagem = horas_para_percentagem(horas)
        else:
            horas = None
            percentagem = valor
        return pessoa_id, percentagem, tipo, horas


class TarefaDialog(QDialog):
    def __init__(self, parent=None, tarefa=None):
        super().__init__(parent)
        self.setWindowTitle("Atividade")
        self.tarefa = tarefa
        self.resize(620, 600)

        # Todos os dados necessários são lidos aqui, dentro da sessão, para
        # guardar apenas valores simples (nunca objetos ligados à base de dados).
        session = get_session()
        try:
            self._clientes = [(c.id, c.nome) for c in session.query(Cliente).order_by(Cliente.nome).all()]
            projetos = session.query(Projeto).options(selectinload(Projeto.cliente)).order_by(Projeto.nome).all()
            self._info_projetos = [
                (p.id, p.nome, p.cliente_id, p.data_inicio, p.data_fim)
                for p in projetos
            ]
            pessoas_ativas = session.query(Pessoa).filter_by(ativo=True).order_by(Pessoa.nome).all()
            self.estados_disponiveis = listar_estados_tarefa(session)

            alocacoes_existentes = []
            pessoas_extra = []
            cliente_inicial = None
            if tarefa is not None and getattr(tarefa, "id", None):
                alocs = session.query(Alocacao).filter_by(tarefa_id=tarefa.id).all()
                alocacoes_existentes = [
                    (a.pessoa_id, float(a.percentagem or 0), a.tipo or "percentagem",
                     float(a.horas) if a.horas is not None else None)
                    for a in alocs
                ]
                ativos_ids = {p.id for p in pessoas_ativas}
                extra_ids = {a[0] for a in alocacoes_existentes} - ativos_ids
                if extra_ids:
                    # pessoas já alocadas mas entretanto marcadas como inativas:
                    # mantêm-se na lista para não perder/trocar a alocação
                    pessoas_extra = session.query(Pessoa).filter(Pessoa.id.in_(extra_ids)).all()
                if tarefa.projeto_id:
                    info = next((i for i in self._info_projetos if i[0] == tarefa.projeto_id), None)
                    cliente_inicial = info[2] if info else None
            self.pessoas = (
                [(p.id, p.nome) for p in pessoas_ativas]
                + [(p.id, f"{p.nome} (inativo)") for p in pessoas_extra]
            )
        finally:
            session.close()

        self._datas_projetos = {i: (ini, fim) for i, _n, _c, ini, fim in self._info_projetos}
        self._cliente_do_projeto = {i: c for i, _n, c, _ini, _fim in self._info_projetos}

        self.nome = QLineEdit(tarefa.nome if tarefa else "")

        # A seguir ao nome, escolhe-se primeiro o Cliente e só depois o
        # Projeto (já filtrado pelo cliente escolhido).
        self.cliente_combo = QComboBox()
        self.cliente_combo.addItem("(todos os clientes)", None)
        for cid, cnome in self._clientes:
            self.cliente_combo.addItem(cnome, cid)
        if cliente_inicial:
            idx = self.cliente_combo.findData(cliente_inicial)
            if idx >= 0:
                self.cliente_combo.setCurrentIndex(idx)

        self.projeto_combo = QComboBox()
        self.cliente_combo.currentIndexChanged.connect(self._repopular_projetos)
        self._repopular_projetos(manter_selecao=tarefa.projeto_id if tarefa else None)

        self.data_inicio = QDateEdit(calendarPopup=True)
        self.data_inicio.setDate(pydate_to_qdate(tarefa.data_inicio if tarefa else None))
        self.data_fim = QDateEdit(calendarPopup=True)
        self.data_fim.setDate(pydate_to_qdate(tarefa.data_fim if tarefa else None))

        # Ao escolher (ativamente) um projeto, as datas passam a ter por
        # defeito as datas do projeto -- mas continuam editáveis à mão depois.
        self.projeto_combo.activated.connect(self._preencher_datas_do_projeto)

        self.estado_combo = QComboBox()
        self.estado_combo.addItems(self.estados_disponiveis)
        if tarefa and tarefa.estado:
            if tarefa.estado not in self.estados_disponiveis:
                self.estado_combo.addItem(tarefa.estado)
            self.estado_combo.setCurrentText(tarefa.estado)

        form = QFormLayout()
        form.addRow("Nome*", self.nome)
        form.addRow("Cliente", self.cliente_combo)
        form.addRow("Projeto", self.projeto_combo)
        form.addRow("Data início", self.data_inicio)
        form.addRow("Data fim", self.data_fim)
        form.addRow("Estado", self.estado_combo)

        # --- Alocações de pessoas ---
        # As linhas ficam coladas ao topo, com o mesmo espaçamento vertical dos
        # restantes campos do formulário: a "mola" no fim impede que o espaço
        # livre da área com scroll seja repartido entre as linhas.
        self.alocacoes_container = QVBoxLayout()
        self.alocacoes_container.setContentsMargins(0, 0, 0, 0)
        self.alocacoes_container.setSpacing(6)
        self.alocacoes_container.addStretch(1)
        self.linhas_alocacao = []

        # Os títulos usam as mesmas proporções das linhas (3 : 2 : 2 + botão de 28 px)
        cabecalho = QHBoxLayout()
        cabecalho.setContentsMargins(0, 0, 0, 0)
        for texto, largura in [("Pessoa", 3), ("Tipo", 2), ("Valor", 2)]:
            lbl = QLabel(texto)
            lbl.setStyleSheet("font-weight: bold; color: #555;")
            cabecalho.addWidget(lbl, largura)
        espaco_botao = QLabel("")
        espaco_botao.setFixedWidth(28)
        cabecalho.addWidget(espaco_botao)

        btn_add = QPushButton("+ Adicionar pessoa")
        btn_add.clicked.connect(lambda: self._adicionar_linha_alocacao())

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self._validar_e_aceitar)
        botoes.rejected.connect(self.reject)

        self._area_alocacoes = QFrame()
        self._area_alocacoes.setLayout(self.alocacoes_container)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._area_alocacoes)
        scroll.setMinimumHeight(160)

        aviso = QLabel("A alocação é sempre relativa a um dia útil de 8 horas (Seg-Sex).")
        aviso.setStyleSheet("color: #666; font-size: 11px;")

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Pessoas alocadas:"))
        layout.addWidget(aviso)
        layout.addLayout(cabecalho)
        layout.addWidget(scroll)
        layout.addWidget(btn_add)
        layout.addWidget(botoes)

        if not self.pessoas:
            btn_add.setEnabled(False)
        elif alocacoes_existentes:
            for pessoa_id, pct, tipo, horas in alocacoes_existentes:
                self._adicionar_linha_alocacao(pessoa_id, pct, tipo, horas)
        else:
            self._adicionar_linha_alocacao()

    def _repopular_projetos(self, _index=None, manter_selecao=None):
        cliente_id = self.cliente_combo.currentData()
        projeto_id_atual = manter_selecao if manter_selecao is not None else self.projeto_combo.currentData()
        self.projeto_combo.blockSignals(True)
        self.projeto_combo.clear()
        self.projeto_combo.addItem("(sem projeto)", None)
        for pid, pnome, pcliente, _ini, _fim in self._info_projetos:
            if cliente_id is not None and pcliente != cliente_id:
                continue
            self.projeto_combo.addItem(pnome, pid)
        if projeto_id_atual:
            idx = self.projeto_combo.findData(projeto_id_atual)
            if idx >= 0:
                self.projeto_combo.setCurrentIndex(idx)
        self.projeto_combo.blockSignals(False)

    def _preencher_datas_do_projeto(self, _index=None):
        datas = self._datas_projetos.get(self.projeto_combo.currentData())
        if datas and datas[0] and datas[1]:
            self.data_inicio.setDate(pydate_to_qdate(datas[0]))
            self.data_fim.setDate(pydate_to_qdate(datas[1]))

    def _adicionar_linha_alocacao(self, pessoa_id=None, percentagem=0, tipo="percentagem", horas=None):
        linha = AlocacaoRowWidget(
            self.pessoas, pessoa_id, percentagem, tipo, horas,
            ao_remover=self._remover_linha_alocacao,
        )
        # insere antes da "mola" final
        self.alocacoes_container.insertWidget(self.alocacoes_container.count() - 1, linha)
        self.linhas_alocacao.append(linha)

    def _remover_linha_alocacao(self, linha):
        if linha in self.linhas_alocacao:
            self.linhas_alocacao.remove(linha)

    def _validar_e_aceitar(self):
        if self.data_fim.date() < self.data_inicio.date():
            QMessageBox.warning(self, "Datas inválidas", "A data de fim não pode ser anterior à data de início.")
            return
        self.accept()

    def dados(self):
        return {
            "nome": self.nome.text().strip(),
            "projeto_id": self.projeto_combo.currentData(),
            "data_inicio": qdate_to_pydate(self.data_inicio.date()),
            "data_fim": qdate_to_pydate(self.data_fim.date()),
            "estado": self.estado_combo.currentText(),
        }

    def alocacoes(self):
        """Lista de (pessoa_id, percentagem, tipo, horas), ignorando linhas vazias."""
        resultado = []
        for linha in self.linhas_alocacao:
            pessoa_id, pct, tipo, horas = linha.dados()
            if pessoa_id is not None and pct > 0:
                resultado.append((pessoa_id, pct, tipo, horas))
        return resultado


class VistaTarefas(BaseCrudWidget):
    modelo = Tarefa

    def __init__(self):
        self.colunas = ["Cliente", "Projeto", "Nome", "Início", "Fim", "Estado", "Pessoas Alocadas"]
        super().__init__("Atividade")

        # --- filtros por Cliente e Projeto, acima da tabela ---
        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Cliente:"))
        self.filtro_cliente = QComboBox()
        filtros.addWidget(self.filtro_cliente)
        filtros.addWidget(QLabel("Projeto:"))
        self.filtro_projeto = QComboBox()
        filtros.addWidget(self.filtro_projeto)
        filtros.addStretch()
        self.layout().insertLayout(1, filtros)

        self.filtro_cliente.currentIndexChanged.connect(self._ao_mudar_filtro_cliente)
        self.filtro_projeto.currentIndexChanged.connect(self.refresh)
        self._popular_filtros()

    def _popular_filtros(self, manter_projeto=False):
        session = get_session()
        try:
            atual_cliente = self.filtro_cliente.currentData() if self.filtro_cliente.count() else None
            self.filtro_cliente.blockSignals(True)
            self.filtro_cliente.clear()
            self.filtro_cliente.addItem("Todos", None)
            for c in session.query(Cliente).order_by(Cliente.nome):
                self.filtro_cliente.addItem(c.nome, c.id)
            if atual_cliente is not None:
                idx = self.filtro_cliente.findData(atual_cliente)
                if idx >= 0:
                    self.filtro_cliente.setCurrentIndex(idx)
            self.filtro_cliente.blockSignals(False)

            atual_projeto = self.filtro_projeto.currentData() if manter_projeto and self.filtro_projeto.count() else None
            query_projetos = session.query(Projeto)
            cliente_id = self.filtro_cliente.currentData()
            if cliente_id:
                query_projetos = query_projetos.filter_by(cliente_id=cliente_id)
            self.filtro_projeto.blockSignals(True)
            self.filtro_projeto.clear()
            self.filtro_projeto.addItem("Todos", None)
            for p in query_projetos.order_by(Projeto.nome):
                self.filtro_projeto.addItem(p.nome, p.id)
            if atual_projeto is not None:
                idx = self.filtro_projeto.findData(atual_projeto)
                if idx >= 0:
                    self.filtro_projeto.setCurrentIndex(idx)
            self.filtro_projeto.blockSignals(False)
        finally:
            session.close()

    def _ao_mudar_filtro_cliente(self):
        self._popular_filtros(manter_projeto=False)
        self.refresh()

    def refresh_filtros(self):
        self._popular_filtros(manter_projeto=True)
        self.refresh()

    def carregar_linhas(self):
        cliente_id = getattr(self, "filtro_cliente", None) and self.filtro_cliente.currentData()
        projeto_id = getattr(self, "filtro_projeto", None) and self.filtro_projeto.currentData()
        session = get_session()
        try:
            query = (
                session.query(Tarefa)
                .options(
                    selectinload(Tarefa.alocacoes).selectinload(Alocacao.pessoa),
                    selectinload(Tarefa.projeto).selectinload(Projeto.cliente),
                )
            )
            if projeto_id:
                query = query.filter(Tarefa.projeto_id == projeto_id)
            elif cliente_id:
                query = query.join(Projeto).filter(Projeto.cliente_id == cliente_id)
            tarefas = query.order_by(Tarefa.data_inicio.desc()).all()

            linhas = []
            for t in tarefas:
                pessoas_txt = ", ".join(
                    f"{a.pessoa.nome} ({fmt_pct(a.percentagem)})" for a in t.alocacoes if a.pessoa
                )
                cliente = t.projeto.cliente.nome if (t.projeto and t.projeto.cliente) else ""
                linhas.append((t, [
                    cliente,
                    t.projeto.nome if t.projeto else "",
                    t.nome, t.data_inicio, t.data_fim, t.estado, pessoas_txt,
                ]))
            return linhas
        finally:
            session.close()

    def abrir_formulario(self, obj=None):
        dialog = TarefaDialog(self, obj)
        if dialog.exec() == QDialog.Accepted:
            dados = dialog.dados()
            if not dados["nome"]:
                return
            alocacoes = dialog.alocacoes()

            try:
                session = get_session()
                try:
                    conflitos = verificar_sobrealocacoes(
                        session,
                        tarefa_id=obj.id if obj else None,
                        data_inicio=dados["data_inicio"],
                        data_fim=dados["data_fim"],
                        alocacoes_novas=alocacoes,
                    )
                finally:
                    session.close()

                if conflitos:
                    resp = QMessageBox.warning(
                        self, "Sobre-alocação detetada",
                        "As seguintes pessoas ficariam alocadas acima de 100% em período sobreposto:\n\n"
                        + "\n".join(conflitos)
                        + "\n\nQueres gravar mesmo assim?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                    )
                    if resp != QMessageBox.Yes:
                        return

                session = get_session()
                try:
                    if obj is None:
                        tarefa = Tarefa(**dados)
                        session.add(tarefa)
                        session.flush()
                    else:
                        tarefa = session.get(Tarefa, obj.id)
                        for k, v in dados.items():
                            setattr(tarefa, k, v)
                        # remove alocações antigas para recriar
                        for a in list(tarefa.alocacoes):
                            session.delete(a)
                        session.flush()

                    for pessoa_id, pct, tipo, horas in alocacoes:
                        session.add(Alocacao(
                            tarefa_id=tarefa.id, pessoa_id=pessoa_id, percentagem=pct,
                            tipo=tipo, horas=horas,
                        ))

                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()
            except Exception as exc:
                QMessageBox.critical(self, "Erro ao gravar atividade", f"Não foi possível gravar:\n\n{exc}")
                return
            self.refresh()

    def eliminar(self, obj):
        try:
            session = get_session()
            try:
                tarefa = session.get(Tarefa, obj.id)
                if tarefa:
                    session.delete(tarefa)
                    session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao eliminar", f"Não foi possível eliminar:\n\n{exc}")
