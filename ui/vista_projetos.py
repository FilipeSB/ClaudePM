from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QTextEdit, QComboBox, QDateEdit,
    QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QMessageBox
)
from PySide6.QtCore import QDate
from datetime import date
from database.db import get_session, listar_estados_projeto, conjunto_datas_feriados
from database.models import Projeto, Cliente
from ui.base_crud import BaseCrudWidget
from utils.calculos import custo_projeto


def qdate_to_pydate(qdate: QDate):
    return qdate.toPython()


def pydate_to_qdate(pdate):
    if pdate is None:
        return QDate.currentDate()
    return QDate(pdate.year, pdate.month, pdate.day)


class ProjetoDialog(QDialog):
    def __init__(self, parent=None, projeto=None):
        super().__init__(parent)
        self.setWindowTitle("Projeto")
        self.projeto = projeto

        session = get_session()
        try:
            self.clientes = session.query(Cliente).order_by(Cliente.nome).all()
            self.estados_disponiveis = listar_estados_projeto(session)
        finally:
            session.close()

        self.nome = QLineEdit(projeto.nome if projeto else "")

        self.cliente_combo = QComboBox()
        self.cliente_combo.addItem("(sem cliente)", None)
        for c in self.clientes:
            self.cliente_combo.addItem(c.nome, c.id)
        if projeto and projeto.cliente_id:
            idx = self.cliente_combo.findData(projeto.cliente_id)
            if idx >= 0:
                self.cliente_combo.setCurrentIndex(idx)

        self.data_inicio = QDateEdit(calendarPopup=True)
        self.data_inicio.setDate(pydate_to_qdate(projeto.data_inicio if projeto else None))
        self.data_fim = QDateEdit(calendarPopup=True)
        self.data_fim.setDate(pydate_to_qdate(projeto.data_fim if projeto else None))

        self.objetivos = QTextEdit(projeto.objetivos if projeto else "")
        self.objetivos.setFixedHeight(80)

        self.estado_combo = QComboBox()
        self.estado_combo.addItems(self.estados_disponiveis)
        if projeto and projeto.estado:
            if projeto.estado not in self.estados_disponiveis:
                # o estado atual já não está na lista configurada (foi
                # removido) -- mantém-se como opção extra para não se
                # perder o valor ao abrir o formulário
                self.estado_combo.addItem(projeto.estado)
            self.estado_combo.setCurrentText(projeto.estado)

        form = QFormLayout()
        form.addRow("Nome*", self.nome)
        form.addRow("Cliente", self.cliente_combo)
        form.addRow("Data início", self.data_inicio)
        form.addRow("Data fim", self.data_fim)
        form.addRow("Objetivos", self.objetivos)
        form.addRow("Estado", self.estado_combo)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self._validar_e_aceitar)
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(botoes)

    def _validar_e_aceitar(self):
        if self.data_fim.date() < self.data_inicio.date():
            QMessageBox.warning(self, "Datas inválidas", "A data de fim não pode ser anterior à data de início.")
            return
        self.accept()

    def dados(self):
        return {
            "nome": self.nome.text().strip(),
            "cliente_id": self.cliente_combo.currentData(),
            "data_inicio": qdate_to_pydate(self.data_inicio.date()),
            "data_fim": qdate_to_pydate(self.data_fim.date()),
            "objetivos": self.objetivos.toPlainText().strip(),
            "estado": self.estado_combo.currentText(),
        }


class VistaProjetos(BaseCrudWidget):
    modelo = Projeto
    def __init__(self):
        self.colunas = ["Nome", "Cliente", "Início", "Fim", "Estado", "Custo Estimado (€)"]
        self.exportavel = True
        self.nome_exportacao = "projetos"
        self._custo_ate_data = None  # None = sem filtro; definido antes do primeiro refresh()
        super().__init__("Projeto")

        # --- controlo de "consultar custos até uma data" ---
        controlo = QHBoxLayout()
        self.check_custo_ate = QCheckBox("Ver custos apenas até uma data:")
        self.data_custo_ate = QDateEdit(calendarPopup=True)
        self.data_custo_ate.setDate(QDate.currentDate())
        self.data_custo_ate.setEnabled(False)
        controlo.addWidget(self.check_custo_ate)
        controlo.addWidget(self.data_custo_ate)
        controlo.addStretch()
        self.layout().insertLayout(1, controlo)

        self.check_custo_ate.toggled.connect(self._ao_alterar_filtro_custo)
        self.data_custo_ate.dateChanged.connect(self._ao_alterar_filtro_custo)

        # --- filtro por Cliente ---
        filtro_layout = QHBoxLayout()
        filtro_layout.addWidget(QLabel("Cliente:"))
        self.filtro_cliente = QComboBox()
        filtro_layout.addWidget(self.filtro_cliente)
        filtro_layout.addStretch()
        self.layout().insertLayout(2, filtro_layout)
        self.filtro_cliente.currentIndexChanged.connect(self.refresh)
        self._popular_filtro_cliente()

    def _popular_filtro_cliente(self):
        session = get_session()
        try:
            atual = self.filtro_cliente.currentData() if self.filtro_cliente.count() else None
            self.filtro_cliente.blockSignals(True)
            self.filtro_cliente.clear()
            self.filtro_cliente.addItem("Todos", None)
            for c in session.query(Cliente).order_by(Cliente.nome):
                self.filtro_cliente.addItem(c.nome, c.id)
            if atual is not None:
                idx = self.filtro_cliente.findData(atual)
                if idx >= 0:
                    self.filtro_cliente.setCurrentIndex(idx)
            self.filtro_cliente.blockSignals(False)
        finally:
            session.close()

    def refresh_filtros(self):
        self._popular_filtro_cliente()
        self.refresh()

    def _ao_alterar_filtro_custo(self):
        self.data_custo_ate.setEnabled(self.check_custo_ate.isChecked())
        self._custo_ate_data = self.data_custo_ate.date().toPython() if self.check_custo_ate.isChecked() else None
        self.refresh()

    def carregar_linhas(self):
        ate_data = self._custo_ate_data
        rotulo_coluna = f"Custo até {ate_data} (€)" if ate_data else "Custo Estimado (€)"
        self.colunas = ["Nome", "Cliente", "Início", "Fim", "Estado", rotulo_coluna]

        cliente_id = getattr(self, "filtro_cliente", None) and self.filtro_cliente.currentData()
        session = get_session()
        try:
            query = session.query(Projeto)
            if cliente_id:
                query = query.filter_by(cliente_id=cliente_id)
            projetos = query.order_by(Projeto.data_inicio.desc()).all()
            feriados = conjunto_datas_feriados(session)
            return [
                (p, [
                    p.nome,
                    p.cliente.nome if p.cliente else "",
                    p.data_inicio, p.data_fim, p.estado,
                    f"{custo_projeto(p, ate_data, feriados):,.2f}",
                ])
                for p in projetos
            ]
        finally:
            session.close()

    def abrir_formulario(self, obj=None):
        dialog = ProjetoDialog(self, obj)
        if dialog.exec() == QDialog.Accepted:
            dados = dialog.dados()
            if not dados["nome"]:
                return

            def gravar():
                session = get_session()
                try:
                    if obj is None:
                        session.add(Projeto(**dados))
                    else:
                        projeto = session.get(Projeto, obj.id)
                        for k, v in dados.items():
                            setattr(projeto, k, v)
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()

            if self.executar_com_seguranca(gravar, "Erro ao gravar projeto"):
                self.refresh()

    def eliminar(self, obj):
        def apagar():
            session = get_session()
            try:
                projeto = session.get(Projeto, obj.id)
                if projeto:
                    session.delete(projeto)
                    session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        self.executar_com_seguranca(apagar, "Erro ao eliminar projeto")
