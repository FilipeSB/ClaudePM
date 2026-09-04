"""
Widget base para ecrãs de listagem + formulário (CRUD) simples.
Cada vista concreta (Cliente, Equipa, Perfil, ...) define as colunas
e o formulário de edição, reutilizando esta estrutura comum.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QHeaderView, QAbstractItemView, QFileDialog
)
from PySide6.QtCore import Qt
from utils.exportacao import exportar_excel, exportar_pdf


class BaseCrudWidget(QWidget):
    """
    Subclasses devem definir:
      - self.colunas: list[str]              -> cabeçalhos da tabela
      - self.get_session()                   -> nova sessão SQLAlchemy
      - self.carregar_linhas() -> list[tuple(obj, list[str])]
      - self.abrir_formulario(obj=None)      -> abre diálogo de criar/editar
      - self.eliminar(obj)                   -> remove o registo
    """

    def __init__(self, titulo: str):
        super().__init__()
        self.titulo = titulo
        if not hasattr(self, "nome_exportacao"):
            self.nome_exportacao = titulo.lower()
        layout = QVBoxLayout(self)

        botoes = QHBoxLayout()
        self.btn_novo = QPushButton("Novo")
        self.btn_editar = QPushButton("Editar")
        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_atualizar = QPushButton("Atualizar lista")
        for b in (self.btn_novo, self.btn_editar, self.btn_eliminar, self.btn_atualizar):
            botoes.addWidget(b)
        botoes.addStretch()

        self.btn_exportar_excel = QPushButton("Exportar Excel")
        self.btn_exportar_pdf = QPushButton("Exportar PDF")
        self.btn_exportar_excel.clicked.connect(self._exportar_excel)
        self.btn_exportar_pdf.clicked.connect(self._exportar_pdf)
        botoes.addWidget(self.btn_exportar_excel)
        botoes.addWidget(self.btn_exportar_pdf)

        layout.addLayout(botoes)

        self.tabela = QTableWidget()
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tabela)

        self.btn_novo.clicked.connect(lambda: self.abrir_formulario(None))
        self.btn_editar.clicked.connect(self._editar_selecionado)
        self.btn_eliminar.clicked.connect(self._eliminar_selecionado)
        self.btn_atualizar.clicked.connect(self.refresh)

        self._objetos = []  # objeto ORM correspondente a cada linha
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self):
        linhas = self.carregar_linhas()
        self.tabela.setColumnCount(len(self.colunas))
        self.tabela.setHorizontalHeaderLabels(self.colunas)
        self.tabela.setRowCount(len(linhas))
        self._objetos = []
        for row, (obj, valores) in enumerate(linhas):
            self._objetos.append(obj)
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor) if valor is not None else "")
                self.tabela.setItem(row, col, item)

    def _linha_selecionada_obj(self):
        linha = self.tabela.currentRow()
        if linha < 0 or linha >= len(self._objetos):
            return None
        return self._objetos[linha]

    def _editar_selecionado(self):
        obj = self._linha_selecionada_obj()
        if obj is None:
            QMessageBox.information(self, "Editar", "Seleciona um registo na tabela.")
            return
        self.abrir_formulario(obj)

    def _eliminar_selecionado(self):
        obj = self._linha_selecionada_obj()
        if obj is None:
            QMessageBox.information(self, "Eliminar", "Seleciona um registo na tabela.")
            return
        resp = QMessageBox.question(
            self, "Confirmar eliminação",
            f"Tens a certeza que queres eliminar este registo de {self.titulo}?"
        )
        if resp == QMessageBox.Yes:
            self.eliminar(obj)
            self.refresh()

    # ------------------------------------------------------------------
    def _tabela_para_linhas(self):
        linhas = []
        for row in range(self.tabela.rowCount()):
            linha = []
            for col in range(self.tabela.columnCount()):
                item = self.tabela.item(row, col)
                linha.append(item.text() if item else "")
            linhas.append(linha)
        return linhas

    def _exportar_excel(self):
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar para Excel", f"{self.nome_exportacao}.xlsx", "Ficheiros Excel (*.xlsx)"
        )
        if not caminho:
            return
        try:
            exportar_excel(caminho, self.titulo, self.colunas, self._tabela_para_linhas())
            QMessageBox.information(self, "Exportação concluída", f"Dados exportados para:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _exportar_pdf(self):
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar para PDF", f"{self.nome_exportacao}.pdf", "Ficheiros PDF (*.pdf)"
        )
        if not caminho:
            return
        try:
            exportar_pdf(caminho, self.titulo, self.colunas, self._tabela_para_linhas())
            QMessageBox.information(self, "Exportação concluída", f"Dados exportados para:\n{caminho}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
