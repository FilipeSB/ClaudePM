from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox, QVBoxLayout
)
from database.db import get_session
from database.models import Equipa
from ui.base_crud import BaseCrudWidget


class EquipaDialog(QDialog):
    def __init__(self, parent=None, equipa=None):
        super().__init__(parent)
        self.setWindowTitle("Equipa")
        self.equipa = equipa

        self.nome = QLineEdit(equipa.nome if equipa else "")
        self.descricao = QTextEdit(equipa.descricao if equipa else "")
        self.descricao.setFixedHeight(80)

        form = QFormLayout()
        form.addRow("Nome*", self.nome)
        form.addRow("Descrição", self.descricao)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(botoes)

    def dados(self):
        return {
            "nome": self.nome.text().strip(),
            "descricao": self.descricao.toPlainText().strip(),
        }


class VistaEquipas(BaseCrudWidget):
    def __init__(self):
        self.colunas = ["ID", "Nome", "Descrição", "Nº Pessoas"]
        super().__init__("Equipa")

    def carregar_linhas(self):
        session = get_session()
        try:
            equipas = session.query(Equipa).order_by(Equipa.nome).all()
            return [
                (e, [e.id, e.nome, e.descricao or "", len(e.pessoas)])
                for e in equipas
            ]
        finally:
            session.close()

    def abrir_formulario(self, obj=None):
        dialog = EquipaDialog(self, obj)
        if dialog.exec() == QDialog.Accepted:
            dados = dialog.dados()
            if not dados["nome"]:
                return

            def gravar():
                session = get_session()
                try:
                    if obj is None:
                        session.add(Equipa(**dados))
                    else:
                        equipa = session.get(Equipa, obj.id)
                        for k, v in dados.items():
                            setattr(equipa, k, v)
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()

            if self.executar_com_seguranca(gravar, "Erro ao gravar equipa"):
                self.refresh()

    def eliminar(self, obj):
        def apagar():
            session = get_session()
            try:
                equipa = session.get(Equipa, obj.id)
                if equipa:
                    session.delete(equipa)
                    session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        self.executar_com_seguranca(apagar, "Erro ao eliminar equipa")
