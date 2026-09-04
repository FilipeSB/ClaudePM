from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QCheckBox, QDialogButtonBox, QVBoxLayout
)
from database.db import get_session
from database.models import Pessoa, Equipa, Perfil
from ui.base_crud import BaseCrudWidget


class PessoaDialog(QDialog):
    def __init__(self, parent=None, pessoa=None):
        super().__init__(parent)
        self.setWindowTitle("Pessoa")
        self.pessoa = pessoa

        session = get_session()
        try:
            self.equipas = session.query(Equipa).order_by(Equipa.nome).all()
            self.perfis = session.query(Perfil).order_by(Perfil.codigo).all()
        finally:
            session.close()

        self.nome = QLineEdit(pessoa.nome if pessoa else "")
        self.email = QLineEdit(pessoa.email if pessoa else "")

        self.equipa_combo = QComboBox()
        self.equipa_combo.addItem("(sem equipa)", None)
        for e in self.equipas:
            self.equipa_combo.addItem(e.nome, e.id)
        if pessoa and pessoa.equipa_id:
            idx = self.equipa_combo.findData(pessoa.equipa_id)
            if idx >= 0:
                self.equipa_combo.setCurrentIndex(idx)

        self.perfil_combo = QComboBox()
        self.perfil_combo.addItem("(sem perfil)", None)
        for p in self.perfis:
            self.perfil_combo.addItem(f"{p.codigo} - {p.designacao}", p.id)
        if pessoa and pessoa.perfil_id:
            idx = self.perfil_combo.findData(pessoa.perfil_id)
            if idx >= 0:
                self.perfil_combo.setCurrentIndex(idx)

        self.ativo = QCheckBox("Ativo")
        self.ativo.setChecked(pessoa.ativo if pessoa else True)

        form = QFormLayout()
        form.addRow("Nome*", self.nome)
        form.addRow("Email", self.email)
        form.addRow("Equipa", self.equipa_combo)
        form.addRow("Perfil (CC01-CC07)", self.perfil_combo)
        form.addRow("", self.ativo)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(botoes)

    def dados(self):
        return {
            "nome": self.nome.text().strip(),
            "email": self.email.text().strip(),
            "equipa_id": self.equipa_combo.currentData(),
            "perfil_id": self.perfil_combo.currentData(),
            "ativo": self.ativo.isChecked(),
        }


class VistaPessoas(BaseCrudWidget):
    def __init__(self):
        self.colunas = ["ID", "Nome", "Equipa", "Perfil", "Email", "Ativo"]
        super().__init__("Pessoa")

    def carregar_linhas(self):
        session = get_session()
        try:
            pessoas = session.query(Pessoa).order_by(Pessoa.nome).all()
            return [
                (p, [
                    p.id, p.nome,
                    p.equipa.nome if p.equipa else "",
                    p.perfil.codigo if p.perfil else "",
                    p.email or "",
                    "Sim" if p.ativo else "Não",
                ])
                for p in pessoas
            ]
        finally:
            session.close()

    def abrir_formulario(self, obj=None):
        dialog = PessoaDialog(self, obj)
        if dialog.exec() == QDialog.Accepted:
            dados = dialog.dados()
            if not dados["nome"]:
                return
            session = get_session()
            try:
                if obj is None:
                    session.add(Pessoa(**dados))
                else:
                    pessoa = session.get(Pessoa, obj.id)
                    for k, v in dados.items():
                        setattr(pessoa, k, v)
                session.commit()
            finally:
                session.close()
            self.refresh()

    def eliminar(self, obj):
        session = get_session()
        try:
            pessoa = session.get(Pessoa, obj.id)
            if pessoa:
                session.delete(pessoa)
                session.commit()
        finally:
            session.close()
