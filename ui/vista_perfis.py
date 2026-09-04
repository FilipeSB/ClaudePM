from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDoubleSpinBox, QDialogButtonBox, QVBoxLayout
)
from datetime import date
from database.db import get_session
from database.models import Perfil
from ui.base_crud import BaseCrudWidget


class PerfilDialog(QDialog):
    def __init__(self, parent=None, perfil=None):
        super().__init__(parent)
        self.setWindowTitle("Perfil de Experiência")
        self.perfil = perfil

        self.codigo = QLineEdit(perfil.codigo if perfil else "")
        self.designacao = QLineEdit(perfil.designacao if perfil else "")
        self.custo_hora = QDoubleSpinBox()
        self.custo_hora.setRange(0, 100000)
        self.custo_hora.setDecimals(2)
        self.custo_hora.setValue(float(perfil.custo_hora) if perfil else 0)
        self.custo_dia = QDoubleSpinBox()
        self.custo_dia.setRange(0, 1000000)
        self.custo_dia.setDecimals(2)
        self.custo_dia.setValue(float(perfil.custo_dia) if perfil else 0)

        form = QFormLayout()
        form.addRow("Código* (ex: CC01)", self.codigo)
        form.addRow("Designação", self.designacao)
        form.addRow("Custo / hora", self.custo_hora)
        form.addRow("Custo / dia", self.custo_dia)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(botoes)

    def dados(self):
        return {
            "codigo": self.codigo.text().strip().upper(),
            "designacao": self.designacao.text().strip(),
            "custo_hora": self.custo_hora.value(),
            "custo_dia": self.custo_dia.value(),
            "data_atualizacao": date.today(),
        }


class VistaPerfis(BaseCrudWidget):
    def __init__(self):
        self.colunas = ["ID", "Código", "Designação", "Custo/Hora", "Custo/Dia", "Atualizado em"]
        super().__init__("Perfil")

    def carregar_linhas(self):
        session = get_session()
        try:
            perfis = session.query(Perfil).order_by(Perfil.codigo).all()
            return [
                (p, [p.id, p.codigo, p.designacao or "", p.custo_hora, p.custo_dia, p.data_atualizacao])
                for p in perfis
            ]
        finally:
            session.close()

    def abrir_formulario(self, obj=None):
        dialog = PerfilDialog(self, obj)
        if dialog.exec() == QDialog.Accepted:
            dados = dialog.dados()
            if not dados["codigo"]:
                return
            session = get_session()
            try:
                if obj is None:
                    session.add(Perfil(**dados))
                else:
                    perfil = session.get(Perfil, obj.id)
                    for k, v in dados.items():
                        setattr(perfil, k, v)
                session.commit()
            finally:
                session.close()
            self.refresh()

    def eliminar(self, obj):
        session = get_session()
        try:
            perfil = session.get(Perfil, obj.id)
            if perfil:
                session.delete(perfil)
                session.commit()
        finally:
            session.close()
