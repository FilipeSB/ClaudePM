from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QDoubleSpinBox, QDateEdit, QDialogButtonBox, QVBoxLayout,
    QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLabel,
    QAbstractItemView
)
from PySide6.QtCore import QDate
from datetime import date
from database.db import get_session
from database.models import Perfil, PerfilCustoHistorico, DATA_BASE_CUSTOS
from ui.base_crud import BaseCrudWidget
from utils.calculos import sincronizar_perfil_com_historico


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

        # Data a partir da qual o novo custo passa a valer (hoje, uma data
        # passada para corrigir o histórico, ou futura para agendar um aumento).
        self.data_vigencia = QDateEdit(calendarPopup=True)
        self.data_vigencia.setDate(QDate.currentDate())
        if perfil:
            form.addRow("Custo em vigor a partir de*", self.data_vigencia)
            aviso = QLabel(
                "Só é criado um novo registo no histórico se o custo/hora ou "
                "custo/dia forem diferentes dos atuais."
            )
            aviso.setWordWrap(True)
            aviso.setStyleSheet("color: #666; font-size: 11px;")
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

    def data_vigencia_selecionada(self) -> date:
        return self.data_vigencia.date().toPython()


class HistoricoCustosDialog(QDialog):
    """Histórico de custos de um perfil, com possibilidade de eliminar registos (mínimo: 1)."""

    def __init__(self, parent, perfil_id, codigo=""):
        super().__init__(parent)
        self.setWindowTitle(f"Histórico de custos — {codigo}")
        self.resize(460, 340)
        self.perfil_id = perfil_id
        self.alterado = False
        self._ids = []

        layout = QVBoxLayout(self)
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(3)
        self.tabela.setHorizontalHeaderLabels(["Em vigor a partir de", "Custo/Hora", "Custo/Dia"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.tabela)

        self.aviso = QLabel("")
        self.aviso.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.aviso)

        botoes = QHBoxLayout()
        self.btn_eliminar = QPushButton("Eliminar registo selecionado")
        self.btn_eliminar.clicked.connect(self._eliminar)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)
        botoes.addWidget(self.btn_eliminar)
        botoes.addStretch()
        botoes.addWidget(fechar)
        layout.addLayout(botoes)

        self._carregar()

    def _carregar(self):
        session = get_session()
        try:
            perfil = session.get(Perfil, self.perfil_id)
            historico = sorted(perfil.historico_custos, key=lambda h: (h.data_alteracao, h.id), reverse=True)
            self._ids = [h.id for h in historico]
            self.tabela.setRowCount(len(historico))
            for row, h in enumerate(historico):
                data_txt = "Início (custo original)" if h.data_alteracao == DATA_BASE_CUSTOS else str(h.data_alteracao)
                self.tabela.setItem(row, 0, QTableWidgetItem(data_txt))
                self.tabela.setItem(row, 1, QTableWidgetItem(f"{float(h.custo_hora or 0):.2f}"))
                self.tabela.setItem(row, 2, QTableWidgetItem(f"{float(h.custo_dia or 0):.2f}"))
        finally:
            session.close()
        so_um = len(self._ids) <= 1
        self.btn_eliminar.setEnabled(not so_um)
        self.aviso.setText("É obrigatório manter pelo menos um registo." if so_um else "")

    def _eliminar(self):
        row = self.tabela.currentRow()
        if row < 0 or row >= len(self._ids):
            QMessageBox.information(self, "Eliminar", "Seleciona um registo na tabela.")
            return
        resp = QMessageBox.question(
            self, "Eliminar registo",
            "Eliminar este registo do histórico? Os custos dos projetos passam a ser "
            "recalculados sem esta alteração."
        )
        if resp != QMessageBox.Yes:
            return
        registo_id = self._ids[row]
        session = get_session()
        try:
            n = session.query(PerfilCustoHistorico).filter_by(perfil_id=self.perfil_id).count()
            if n <= 1:
                QMessageBox.warning(self, "Não permitido", "Tem de existir pelo menos um registo no histórico.")
                return
            registo = session.get(PerfilCustoHistorico, registo_id)
            if registo is not None:
                session.delete(registo)
                session.flush()
            perfil = session.get(Perfil, self.perfil_id)
            session.expire(perfil, ["historico_custos"])
            sincronizar_perfil_com_historico(perfil)
            session.commit()
            self.alterado = True
        except Exception as exc:
            session.rollback()
            QMessageBox.critical(self, "Erro ao eliminar", f"Não foi possível eliminar:\n\n{exc}")
        finally:
            session.close()
        self._carregar()


class VistaPerfis(BaseCrudWidget):
    modelo = Perfil

    def __init__(self):
        self.colunas = ["Código", "Designação", "Custo/Hora", "Custo/Dia", "Última alteração"]
        super().__init__("Perfil")

        self.btn_historico = QPushButton("Ver histórico de custos")
        self.btn_historico.clicked.connect(self._ver_historico)
        self.layout().itemAt(0).layout().addWidget(self.btn_historico)

    def carregar_linhas(self):
        session = get_session()
        try:
            perfis = session.query(Perfil).order_by(Perfil.codigo).all()
            return [
                (p, [p.codigo, p.designacao or "", f"{float(p.custo_hora or 0):.2f}",
                     f"{float(p.custo_dia or 0):.2f}", p.data_atualizacao])
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
            data_vigencia = dialog.data_vigencia_selecionada() if obj else date.today()

            def gravar():
                session = get_session()
                try:
                    if obj is None:
                        perfil = Perfil(**dados, data_atualizacao=data_vigencia)
                        session.add(perfil)
                        session.flush()
                        session.add(PerfilCustoHistorico(
                            perfil_id=perfil.id, custo_hora=dados["custo_hora"],
                            custo_dia=dados["custo_dia"], data_alteracao=DATA_BASE_CUSTOS,
                        ))
                    else:
                        perfil = session.get(Perfil, obj.id)
                        custo_mudou = (
                            float(perfil.custo_hora or 0) != dados["custo_hora"]
                            or float(perfil.custo_dia or 0) != dados["custo_dia"]
                        )
                        perfil.codigo = dados["codigo"]
                        perfil.designacao = dados["designacao"]
                        if custo_mudou:
                            session.add(PerfilCustoHistorico(
                                perfil_id=perfil.id, custo_hora=dados["custo_hora"],
                                custo_dia=dados["custo_dia"], data_alteracao=data_vigencia,
                            ))
                            session.flush()
                            session.expire(perfil, ["historico_custos"])
                            # o custo "atual" passa a ser o que está em vigor HOJE
                            sincronizar_perfil_com_historico(perfil)
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()

            if self.executar_com_seguranca(gravar, "Erro ao gravar perfil"):
                self.refresh()

    def eliminar(self, obj):
        def apagar():
            session = get_session()
            try:
                perfil = session.get(Perfil, obj.id)
                if perfil:
                    session.delete(perfil)
                    session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        self.executar_com_seguranca(apagar, "Erro ao eliminar perfil")

    def _ver_historico(self):
        registo_id = self._id_selecionado()
        if registo_id is None:
            QMessageBox.information(self, "Histórico de custos", "Seleciona um perfil na tabela.")
            return
        codigo = self.tabela.item(self.tabela.currentRow(), 0).text()
        dialog = HistoricoCustosDialog(self, int(registo_id), codigo)
        dialog.exec()
        if dialog.alterado:
            self.refresh()
