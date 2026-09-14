from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDoubleSpinBox, QDialogButtonBox, QVBoxLayout,
    QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from datetime import date
from database.db import get_session
from database.models import Perfil, PerfilCustoHistorico
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

        if perfil:
            aviso = QLineEdit(
                f"Alterar os custos regista automaticamente a data de hoje ({date.today()}) "
                "no histórico de custos deste perfil.",
                readOnly=True,
            )
            aviso.setStyleSheet("color: #666; border: none; background: transparent;")
            form.addRow("", aviso)

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
        }


class HistoricoCustosDialog(QDialog):
    def __init__(self, parent, perfil):
        super().__init__(parent)
        self.setWindowTitle(f"Histórico de custos — {perfil.codigo}")
        self.resize(420, 320)

        layout = QVBoxLayout(self)
        tabela = QTableWidget()
        tabela.setColumnCount(3)
        tabela.setHorizontalHeaderLabels(["Data de alteração", "Custo/Hora", "Custo/Dia"])
        tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tabela.setEditTriggers(QTableWidget.NoEditTriggers)

        historico = sorted(perfil.historico_custos, key=lambda h: h.data_alteracao, reverse=True)
        tabela.setRowCount(len(historico))
        for row, h in enumerate(historico):
            tabela.setItem(row, 0, QTableWidgetItem(str(h.data_alteracao)))
            tabela.setItem(row, 1, QTableWidgetItem(f"{h.custo_hora:.2f}"))
            tabela.setItem(row, 2, QTableWidgetItem(f"{h.custo_dia:.2f}"))

        layout.addWidget(tabela)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)
        layout.addWidget(fechar)


class VistaPerfis(BaseCrudWidget):
    def __init__(self):
        self.colunas = ["ID", "Código", "Designação", "Custo/Hora", "Custo/Dia", "Última alteração"]
        super().__init__("Perfil")

        self.btn_historico = QPushButton("Ver histórico de custos")
        self.btn_historico.clicked.connect(self._ver_historico)
        self.layout().itemAt(0).layout().addWidget(self.btn_historico)

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
            hoje = date.today()
            session = get_session()
            try:
                if obj is None:
                    perfil = Perfil(**dados, data_atualizacao=hoje)
                    session.add(perfil)
                    session.flush()
                    session.add(PerfilCustoHistorico(
                        perfil_id=perfil.id, custo_hora=perfil.custo_hora,
                        custo_dia=perfil.custo_dia, data_alteracao=hoje,
                    ))
                else:
                    perfil = session.get(Perfil, obj.id)
                    custo_mudou = (
                        float(perfil.custo_hora or 0) != dados["custo_hora"]
                        or float(perfil.custo_dia or 0) != dados["custo_dia"]
                    )
                    for k, v in dados.items():
                        setattr(perfil, k, v)
                    if custo_mudou:
                        perfil.data_atualizacao = hoje
                        session.add(PerfilCustoHistorico(
                            perfil_id=perfil.id, custo_hora=perfil.custo_hora,
                            custo_dia=perfil.custo_dia, data_alteracao=hoje,
                        ))
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

    def _ver_historico(self):
        obj = self._linha_selecionada_obj()
        if obj is None:
            QMessageBox.information(self, "Histórico de custos", "Seleciona um perfil na tabela.")
            return
        session = get_session()
        try:
            perfil = session.get(Perfil, obj.id)
            dialog = HistoricoCustosDialog(self, perfil)
            dialog.exec()
        finally:
            session.close()
