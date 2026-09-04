from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QFileDialog, QMessageBox
)
from PySide6.QtGui import QColor
from datetime import date
from database.db import get_session
from database.models import Pessoa
from utils.exportacao import exportar_excel, exportar_pdf


class VistaAlocacao(QWidget):
    """
    Mostra, para cada pessoa ativa, a soma das percentagens de alocação
    em tarefas correntes (cuja data de hoje esteja entre início e fim),
    assinalando visualmente sobre-alocação (>100%).
    """

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        topo = QHBoxLayout()
        topo.addWidget(QLabel("Percentagem de alocação atual (tarefas em curso hoje) por pessoa"))
        topo.addStretch()
        btn_atualizar = QPushButton("Atualizar")
        btn_atualizar.clicked.connect(self.refresh)
        topo.addWidget(btn_atualizar)

        btn_excel = QPushButton("Exportar Excel")
        btn_excel.clicked.connect(self._exportar_excel)
        topo.addWidget(btn_excel)

        btn_pdf = QPushButton("Exportar PDF")
        btn_pdf.clicked.connect(self._exportar_pdf)
        topo.addWidget(btn_pdf)

        layout.addLayout(topo)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(5)
        self.tabela.setHorizontalHeaderLabels(
            ["Pessoa", "Equipa", "Perfil", "% Alocada (hoje)", "Detalhe das Tarefas"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tabela)

        self.refresh()

    def refresh(self):
        hoje = date.today()
        session = get_session()
        try:
            pessoas = session.query(Pessoa).filter_by(ativo=True).order_by(Pessoa.nome).all()
            self.tabela.setRowCount(len(pessoas))

            for row, pessoa in enumerate(pessoas):
                total = 0.0
                detalhe = []
                for a in pessoa.alocacoes:
                    t = a.tarefa
                    if t and t.data_inicio and t.data_fim and t.data_inicio <= hoje <= t.data_fim:
                        total += float(a.percentagem or 0)
                        detalhe.append(f"{t.nome} ({a.percentagem}%)")

                self.tabela.setItem(row, 0, QTableWidgetItem(pessoa.nome))
                self.tabela.setItem(row, 1, QTableWidgetItem(pessoa.equipa.nome if pessoa.equipa else ""))
                self.tabela.setItem(row, 2, QTableWidgetItem(pessoa.perfil.codigo if pessoa.perfil else ""))

                item_pct = QTableWidgetItem(f"{total:.0f}%")
                if total > 100:
                    item_pct.setBackground(QColor(255, 190, 190))   # vermelho claro - sobre-alocada
                elif total == 100:
                    item_pct.setBackground(QColor(200, 240, 200))   # verde - alocação total
                elif total == 0:
                    item_pct.setBackground(QColor(230, 230, 230))   # cinza - sem alocação
                else:
                    item_pct.setBackground(QColor(255, 245, 200))   # amarelo - parcial
                self.tabela.setItem(row, 3, item_pct)

                self.tabela.setItem(row, 4, QTableWidgetItem(", ".join(detalhe)))
        finally:
            session.close()

    # ------------------------------------------------------------------
    def _colunas(self):
        return [self.tabela.horizontalHeaderItem(c).text() for c in range(self.tabela.columnCount())]

    def _linhas(self):
        linhas = []
        for row in range(self.tabela.rowCount()):
            linha = []
            for col in range(self.tabela.columnCount()):
                item = self.tabela.item(row, col)
                linha.append(item.text() if item else "")
            linhas.append(linha)
        return linhas

    def _exportar_excel(self):
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar para Excel", "alocacao.xlsx", "Ficheiros Excel (*.xlsx)")
        if not caminho:
            return
        try:
            exportar_excel(caminho, "Alocação", self._colunas(), self._linhas())
            QMessageBox.information(self, "Exportação concluída", f"Dados exportados para:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _exportar_pdf(self):
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar para PDF", "alocacao.pdf", "Ficheiros PDF (*.pdf)")
        if not caminho:
            return
        try:
            exportar_pdf(caminho, "Alocação", self._colunas(), self._linhas())
            QMessageBox.information(self, "Exportação concluída", f"Dados exportados para:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
