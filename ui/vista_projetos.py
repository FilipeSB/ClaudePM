from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QTextEdit, QComboBox, QDateEdit,
    QDialogButtonBox, QVBoxLayout, QMessageBox
)
from PySide6.QtCore import QDate
from database.db import get_session
from database.models import Projeto, Cliente, ESTADOS_PROJETO
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
        self.estado_combo.addItems(ESTADOS_PROJETO)
        if projeto and projeto.estado in ESTADOS_PROJETO:
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
    def __init__(self):
        self.colunas = ["ID", "Nome", "Cliente", "Início", "Fim", "Estado", "Custo Estimado (€)"]
        self.exportavel = True
        self.nome_exportacao = "projetos"
        super().__init__("Projeto")

    def carregar_linhas(self):
        session = get_session()
        try:
            projetos = session.query(Projeto).order_by(Projeto.data_inicio.desc()).all()
            return [
                (p, [
                    p.id, p.nome,
                    p.cliente.nome if p.cliente else "",
                    p.data_inicio, p.data_fim, p.estado,
                    f"{custo_projeto(p):,.2f}",
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
            session = get_session()
            try:
                if obj is None:
                    session.add(Projeto(**dados))
                else:
                    projeto = session.get(Projeto, obj.id)
                    for k, v in dados.items():
                        setattr(projeto, k, v)
                session.commit()
            finally:
                session.close()
            self.refresh()

    def eliminar(self, obj):
        session = get_session()
        try:
            projeto = session.get(Projeto, obj.id)
            if projeto:
                session.delete(projeto)
                session.commit()
        finally:
            session.close()
