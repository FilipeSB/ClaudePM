"""Diálogo para gerir feriados: adicionar/remover manualmente, ou importar da internet."""
from datetime import date

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QDateEdit, QComboBox, QSpinBox, QLabel,
    QMessageBox, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import QDate, Qt

from database.db import get_session
from database.models import Feriado
from utils.feriados import importar_feriados_internet, PAISES_DISPONIVEIS


class GerirFeriadosDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feriados")
        self.resize(460, 480)
        self.alterado = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Feriados marcados no Calendário com uma cor diferente. Podes "
            "adicioná-los manualmente ou importá-los automaticamente da internet."
        ))

        # --- importar da internet ---
        linha_importar = QHBoxLayout()
        linha_importar.addWidget(QLabel("Importar feriados de:"))
        self.combo_pais = QComboBox()
        for codigo, nome in PAISES_DISPONIVEIS:
            self.combo_pais.addItem(nome, codigo)
        linha_importar.addWidget(self.combo_pais)
        self.spin_ano = QSpinBox()
        self.spin_ano.setRange(2000, 2100)
        self.spin_ano.setValue(date.today().year)
        linha_importar.addWidget(self.spin_ano)
        btn_importar = QPushButton("Importar da internet")
        btn_importar.clicked.connect(self._importar)
        linha_importar.addWidget(btn_importar)
        layout.addLayout(linha_importar)

        aviso_internet = QLabel(
            "Requer ligação à internet. Se a importação falhar, podes sempre "
            "adicionar os feriados manualmente abaixo."
        )
        aviso_internet.setWordWrap(True)
        aviso_internet.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(aviso_internet)

        # --- tabela ---
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(2)
        self.tabela.setHorizontalHeaderLabels(["Data", "Descrição"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabela.setSortingEnabled(True)
        layout.addWidget(self.tabela)

        # --- adicionar manualmente ---
        linha_nova = QHBoxLayout()
        self.data_nova = QDateEdit(calendarPopup=True)
        self.data_nova.setDate(QDate.currentDate())
        self.descricao_nova = QLineEdit()
        self.descricao_nova.setPlaceholderText("Descrição (opcional)")
        btn_adicionar = QPushButton("Adicionar")
        btn_adicionar.clicked.connect(self._adicionar)
        linha_nova.addWidget(self.data_nova)
        linha_nova.addWidget(self.descricao_nova)
        linha_nova.addWidget(btn_adicionar)
        layout.addLayout(linha_nova)

        botoes = QHBoxLayout()
        btn_remover = QPushButton("Remover selecionado")
        btn_remover.clicked.connect(self._remover)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)
        botoes.addWidget(btn_remover)
        botoes.addStretch()
        botoes.addWidget(fechar)
        layout.addLayout(botoes)

        self._carregar()

    def _carregar(self):
        session = get_session()
        try:
            feriados = session.query(Feriado).order_by(Feriado.data).all()
            self.tabela.setSortingEnabled(False)
            self.tabela.setRowCount(len(feriados))
            for row, f in enumerate(feriados):
                item_data = QTableWidgetItem(str(f.data))
                item_data.setData(Qt.UserRole, f.id)
                self.tabela.setItem(row, 0, item_data)
                self.tabela.setItem(row, 1, QTableWidgetItem(f.descricao or ""))
            self.tabela.setSortingEnabled(True)
        finally:
            session.close()

    def _adicionar(self):
        data_sel = self.data_nova.date().toPython()
        descricao = self.descricao_nova.text().strip()
        session = get_session()
        try:
            feriado = session.query(Feriado).filter_by(data=data_sel).first()
            if feriado is None:
                feriado = Feriado(data=data_sel)
                session.add(feriado)
            feriado.descricao = descricao
            session.commit()
        except Exception as exc:
            session.rollback()
            QMessageBox.critical(self, "Erro", f"Não foi possível adicionar:\n\n{exc}")
            return
        finally:
            session.close()
        self.descricao_nova.clear()
        self.alterado = True
        self._carregar()

    def _remover(self):
        row = self.tabela.currentRow()
        if row < 0:
            QMessageBox.information(self, "Remover", "Seleciona um feriado na tabela.")
            return
        feriado_id = self.tabela.item(row, 0).data(Qt.UserRole)
        session = get_session()
        try:
            feriado = session.get(Feriado, feriado_id)
            if feriado is not None:
                session.delete(feriado)
                session.commit()
        except Exception as exc:
            session.rollback()
            QMessageBox.critical(self, "Erro", f"Não foi possível remover:\n\n{exc}")
            return
        finally:
            session.close()
        self.alterado = True
        self._carregar()

    def _importar(self):
        ano = self.spin_ano.value()
        pais_codigo = self.combo_pais.currentData()
        pais_nome = self.combo_pais.currentText()
        session = get_session()
        try:
            n = importar_feriados_internet(session, ano, pais_codigo)
        except Exception as exc:
            QMessageBox.critical(
                self, "Erro ao importar",
                f"Não foi possível importar os feriados de {pais_nome} ({ano}) da internet:\n\n{exc}\n\n"
                "Verifica a ligação à internet, ou adiciona os feriados manualmente abaixo."
            )
            return
        finally:
            session.close()
        self.alterado = True
        self._carregar()
        QMessageBox.information(self, "Importação concluída", f"Importados/atualizados {n} feriados de {pais_nome} ({ano}).")
