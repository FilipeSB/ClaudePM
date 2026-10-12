"""
Widget base para ecrãs de listagem + formulário (CRUD).

Notas de robustez:
- A tabela guarda em cada linha apenas o ID (um inteiro simples) do registo,
  não o objeto da base de dados. Ao editar/eliminar, o registo é lido de novo
  da base de dados, por isso nunca se trabalha com dados desatualizados.
- A ordenação por coluna é nativa do Qt; como o ID viaja com a linha,
  Editar/Eliminar atuam sempre sobre o registo certo depois de ordenar.
- O ID não é mostrado ao utilizador.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QPushButton, QMessageBox,
    QHeaderView, QAbstractItemView, QFileDialog
)
from PySide6.QtCore import Qt
from database.db import get_session
from ui.itens import ItemOrdenavel
from utils.exportacao import exportar_excel, exportar_pdf


class BaseCrudWidget(QWidget):
    """
    Subclasses devem definir:
      - modelo: classe do modelo (Cliente, Equipa, ...)
      - self.colunas: list[str]  (sem ID)
      - carregar_linhas() -> list[tuple(obj, list)]  (obj só precisa de .id)
      - abrir_formulario(obj=None)
      - eliminar(obj)
    """
    modelo = None

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
        # -1 = sem ordenação inicial (mantém a ordem devolvida pela consulta)
        self.tabela.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self.tabela.setSortingEnabled(True)
        layout.addWidget(self.tabela)

        self.tabela.cellDoubleClicked.connect(lambda row, col: self._editar_selecionado())

        self.btn_novo.clicked.connect(lambda: self.abrir_formulario(None))
        self.btn_editar.clicked.connect(self._editar_selecionado)
        self.btn_eliminar.clicked.connect(self._eliminar_selecionado)
        self.btn_atualizar.clicked.connect(self.refresh)

        self.refresh()

    # ------------------------------------------------------------------
    def executar_com_seguranca(self, funcao, titulo_erro="Erro"):
        """Executa 'funcao'; se falhar, mostra o erro em vez de o deixar propagar."""
        try:
            funcao()
            return True
        except Exception as exc:
            QMessageBox.critical(self, titulo_erro, f"Não foi possível concluir a operação:\n\n{exc}")
            return False

    def refresh(self):
        linhas = self.carregar_linhas()

        # Sem ordenação ativa durante o preenchimento (evita reentrâncias do Qt)
        self.tabela.setSortingEnabled(False)
        self.tabela.clearContents()
        self.tabela.setColumnCount(len(self.colunas))
        self.tabela.setHorizontalHeaderLabels(self.colunas)
        self.tabela.setRowCount(len(linhas))
        for row, (obj, valores) in enumerate(linhas):
            registo_id = getattr(obj, "id", None)
            for col, valor in enumerate(valores):
                item = ItemOrdenavel(str(valor) if valor is not None else "")
                if col == 0 and registo_id is not None:
                    item.setData(Qt.UserRole, int(registo_id))
                self.tabela.setItem(row, col, item)
        self.tabela.setSortingEnabled(True)

    # ------------------------------------------------------------------
    def _id_selecionado(self):
        linha = self.tabela.currentRow()
        if linha < 0:
            return None
        item = self.tabela.item(linha, 0)
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def obter_para_edicao(self, registo_id):
        """Lê o registo (atualizado) da base de dados, desligado da sessão."""
        session = get_session()
        try:
            obj = session.get(self.modelo, registo_id)
            if obj is not None:
                session.expunge(obj)
            return obj
        finally:
            session.close()

    def _linha_selecionada_obj(self):
        registo_id = self._id_selecionado()
        if registo_id is None:
            return None
        return self.obter_para_edicao(int(registo_id))

    def editar_por_id(self, registo_id):
        """Abre o formulário de edição de um registo (usado também pelo Calendário)."""
        obj = self.obter_para_edicao(int(registo_id))
        if obj is None:
            QMessageBox.information(self, "Editar", "O registo já não existe.")
            return
        self.abrir_formulario(obj)

    def _editar_selecionado(self):
        registo_id = self._id_selecionado()
        if registo_id is None:
            QMessageBox.information(self, "Editar", "Seleciona um registo na tabela.")
            return
        self.editar_por_id(registo_id)

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
