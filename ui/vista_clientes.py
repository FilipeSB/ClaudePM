from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QDialogButtonBox, QVBoxLayout
)
from database.db import get_session
from database.models import Cliente
from ui.base_crud import BaseCrudWidget


class ClienteDialog(QDialog):
    def __init__(self, parent=None, cliente=None):
        super().__init__(parent)
        self.setWindowTitle("Cliente")
        self.cliente = cliente

        self.nome = QLineEdit(cliente.nome if cliente else "")
        self.contacto = QLineEdit(cliente.contacto if cliente else "")
        self.ativo = QCheckBox("Ativo")
        self.ativo.setChecked(cliente.ativo if cliente else True)

        form = QFormLayout()
        form.addRow("Nome*", self.nome)
        form.addRow("Contacto", self.contacto)
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
            "contacto": self.contacto.text().strip(),
            "ativo": self.ativo.isChecked(),
        }


class VistaClientes(BaseCrudWidget):
    def __init__(self):
        self.colunas = ["ID", "Nome", "Contacto", "Ativo"]
        super().__init__("Cliente")

    def carregar_linhas(self):
        session = get_session()
        try:
            clientes = session.query(Cliente).order_by(Cliente.nome).all()
            return [
                (c, [c.id, c.nome, c.contacto or "", "Sim" if c.ativo else "Não"])
                for c in clientes
            ]
        finally:
            session.close()

    def abrir_formulario(self, obj=None):
        dialog = ClienteDialog(self, obj)
        if dialog.exec() == QDialog.Accepted:
            dados = dialog.dados()
            if not dados["nome"]:
                return

            def gravar():
                session = get_session()
                try:
                    if obj is None:
                        session.add(Cliente(**dados))
                    else:
                        cliente = session.get(Cliente, obj.id)
                        for k, v in dados.items():
                            setattr(cliente, k, v)
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()

            if self.executar_com_seguranca(gravar, "Erro ao gravar cliente"):
                self.refresh()

    def eliminar(self, obj):
        def apagar():
            session = get_session()
            try:
                cliente = session.get(Cliente, obj.id)
                if cliente:
                    session.delete(cliente)
                    session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        self.executar_com_seguranca(apagar, "Erro ao eliminar cliente")
