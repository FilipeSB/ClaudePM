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


def _tentar_converter_numero(texto: str):
    """
    Tenta interpretar o texto como número, para permitir ordenação numérica
    correta em colunas como ID, custos ("2,520.00") ou percentagens ("70%").
    Devolve None se não for possível interpretar como número.
    """
    t = texto.strip()
    if not t:
        return None
    t_limpo = t.rstrip("%").replace(",", "")
    try:
        return float(t_limpo)
    except ValueError:
        return None


class ItemOrdenavel(QTableWidgetItem):
    """
    QTableWidgetItem que ordena numericamente quando ambos os valores
    comparados parecem números (mesmo com formatação como "2,520.00" ou
    "70%"), e cai para ordenação alfabética normal nos restantes casos
    (texto, e também datas no formato ISO "AAAA-MM-DD", que já ordenam
    corretamente como texto).
    """

    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            a = _tentar_converter_numero(self.text())
            b = _tentar_converter_numero(other.text())
            if a is not None and b is not None:
                return a < b
            return self.text() < other.text()
        return super().__lt__(other)


class BaseCrudWidget(QWidget):
    """
    Subclasses devem definir:
      - self.colunas: list[str]              -> cabeçalhos da tabela
      - self.get_session()                   -> nova sessão SQLAlchemy
      - self.carregar_linhas() -> list[tuple(obj, list[str])]
      - self.abrir_formulario(obj=None)      -> abre diálogo de criar/editar
      - self.eliminar(obj)                   -> remove o registo

    A tabela suporta ordenação por qualquer coluna (clicando no cabeçalho).
    Como a ordenação nativa do Qt reordena as LINHAS (incluindo os dados
    associados a cada item), a associação obj-linha é guardada como dados
    (Qt.UserRole) na primeira célula de cada linha, em vez de depender de
    um índice de lista paralelo -- isso garante que Editar/Eliminar atuam
    sempre sobre o registo certo, mesmo depois de ordenar por qualquer coluna.
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
        self.tabela.setSortingEnabled(True)
        layout.addWidget(self.tabela)

        self.btn_novo.clicked.connect(lambda: self.abrir_formulario(None))
        self.btn_editar.clicked.connect(self._editar_selecionado)
        self.btn_eliminar.clicked.connect(self._eliminar_selecionado)
        self.btn_atualizar.clicked.connect(self.refresh)

        self.refresh()

    # ------------------------------------------------------------------
    def executar_com_seguranca(self, funcao, titulo_erro="Erro"):
        """
        Executa 'funcao' (que deve gerir a sua própria sessão, incluindo
        commit) e, se ocorrer qualquer excepção, mostra um erro ao
        utilizador em vez de a deixar propagar -- o que, sem tratamento,
        poderia fazer a aplicação inteira fechar sem qualquer aviso.
        Devolve True se correu sem erro, False caso contrário.
        """
        try:
            funcao()
            return True
        except Exception as exc:
            QMessageBox.critical(self, titulo_erro, f"Não foi possível concluir a operação:\n\n{exc}")
            return False

    def refresh(self):
        linhas = self.carregar_linhas()

        # Desativar a ordenação durante o preenchimento evita problemas de
        # reentrância do Qt ao inserir linhas numa tabela já ordenada.
        self.tabela.setSortingEnabled(False)
        self.tabela.setColumnCount(len(self.colunas))
        self.tabela.setHorizontalHeaderLabels(self.colunas)
        self.tabela.setRowCount(len(linhas))
        for row, (obj, valores) in enumerate(linhas):
            for col, valor in enumerate(valores):
                item = ItemOrdenavel(str(valor) if valor is not None else "")
                if col == 0:
                    item.setData(Qt.UserRole, obj)
                self.tabela.setItem(row, col, item)
        self.tabela.setSortingEnabled(True)

    def _linha_selecionada_obj(self):
        linha = self.tabela.currentRow()
        if linha < 0:
            return None
        item = self.tabela.item(linha, 0)
        return item.data(Qt.UserRole) if item else None

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
