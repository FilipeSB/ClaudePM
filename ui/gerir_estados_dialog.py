"""
Diálogo genérico para gerir a lista de estados possíveis (de Projeto ou de
Tarefa): adicionar, renomear, remover e reordenar.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QMessageBox, QLabel
)
from PySide6.QtCore import Qt


class GerirEstadosDialog(QDialog):
    def __init__(self, parent, titulo, modelo_estado, campo_uso_estado, session_factory):
        """
        modelo_estado: classe do modelo (EstadoProjeto ou EstadoTarefa).
        campo_uso_estado: função(session, nome_estado) -> int, nº de
            registos (Projeto/Tarefa) que atualmente usam este estado --
            usada para avisar antes de remover um estado em uso.
        session_factory: função que devolve uma nova sessão (get_session).
        """
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(380, 420)
        self.modelo_estado = modelo_estado
        self.campo_uso_estado = campo_uso_estado
        self.session_factory = session_factory
        self.alterado = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Adiciona, renomeia, remove ou reordena os estados disponíveis. "
            "Registos existentes com um estado removido mantêm o valor antigo."
        ))

        self.lista = QListWidget()
        self.lista.currentItemChanged.connect(self._ao_selecionar)
        layout.addWidget(self.lista)

        linha_nova = QHBoxLayout()
        self.campo_novo = QLineEdit()
        self.campo_novo.setPlaceholderText("Nome do novo estado...")
        btn_adicionar = QPushButton("Adicionar")
        btn_adicionar.clicked.connect(self._adicionar)
        linha_nova.addWidget(self.campo_novo)
        linha_nova.addWidget(btn_adicionar)
        layout.addLayout(linha_nova)

        botoes = QHBoxLayout()
        btn_renomear = QPushButton("Renomear selecionado")
        btn_remover = QPushButton("Remover selecionado")
        btn_subir = QPushButton("▲ Subir")
        btn_descer = QPushButton("▼ Descer")
        for b in (btn_renomear, btn_remover, btn_subir, btn_descer):
            botoes.addWidget(b)
        layout.addLayout(botoes)

        btn_renomear.clicked.connect(self._renomear)
        btn_remover.clicked.connect(self._remover)
        btn_subir.clicked.connect(lambda: self._mover(-1))
        btn_descer.clicked.connect(lambda: self._mover(1))

        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.accept)
        layout.addWidget(btn_fechar)

        self._carregar()

    def _carregar(self):
        self.lista.clear()
        session = self.session_factory()
        try:
            estados = session.query(self.modelo_estado).order_by(self.modelo_estado.ordem).all()
            for e in estados:
                item = QListWidgetItem(e.nome)
                item.setData(Qt.UserRole, e.id)
                self.lista.addItem(item)
        finally:
            session.close()

    def _adicionar(self):
        nome = self.campo_novo.text().strip()
        if not nome:
            return
        session = self.session_factory()
        try:
            if session.query(self.modelo_estado).filter_by(nome=nome).first():
                QMessageBox.information(self, "Já existe", "Já existe um estado com esse nome.")
                return
            maior_ordem = session.query(self.modelo_estado).count()
            session.add(self.modelo_estado(nome=nome, ordem=maior_ordem))
            session.commit()
        finally:
            session.close()
        self.campo_novo.clear()
        self.alterado = True
        self._carregar()

    def _ao_selecionar(self, item_atual, _item_anterior):
        """Ao selecionar um estado, o campo de texto passa a mostrar o nome
        atual -- fica pronto a editar e a usar em 'Renomear selecionado'."""
        if item_atual is not None:
            self.campo_novo.setText(item_atual.text())

    def _item_selecionado_id(self):
        item = self.lista.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _renomear(self):
        estado_id = self._item_selecionado_id()
        if estado_id is None:
            QMessageBox.information(self, "Renomear", "Seleciona um estado na lista.")
            return
        session = self.session_factory()
        try:
            estado = session.get(self.modelo_estado, estado_id)
            nome_antigo = estado.nome
            novo_nome = self.campo_novo.text().strip() or nome_antigo
            if novo_nome != nome_antigo:
                estado.nome = novo_nome
                session.commit()
                self.alterado = True
        finally:
            session.close()
        self._carregar()

    def _remover(self):
        estado_id = self._item_selecionado_id()
        if estado_id is None:
            QMessageBox.information(self, "Remover", "Seleciona um estado na lista.")
            return
        session = self.session_factory()
        try:
            estado = session.get(self.modelo_estado, estado_id)
            nome = estado.nome
            n_uso = self.campo_uso_estado(session, nome)
            if n_uso:
                resp = QMessageBox.question(
                    self, "Estado em uso",
                    f"O estado '{nome}' está atualmente atribuído a {n_uso} registo(s). "
                    "Esses registos mantêm o valor '{nome}' mesmo depois de removido "
                    "desta lista (só deixa de aparecer nas opções para novos registos).\n\n"
                    "Remover mesmo assim?"
                )
                if resp != QMessageBox.Yes:
                    return
            session.delete(estado)
            session.commit()
            self.alterado = True
        finally:
            session.close()
        self._carregar()

    def _mover(self, direcao):
        estado_id = self._item_selecionado_id()
        if estado_id is None:
            return
        session = self.session_factory()
        try:
            estados = session.query(self.modelo_estado).order_by(self.modelo_estado.ordem).all()
            posicoes = {e.id: i for i, e in enumerate(estados)}
            pos_atual = posicoes.get(estado_id)
            nova_pos = pos_atual + direcao
            if pos_atual is None or nova_pos < 0 or nova_pos >= len(estados):
                return
            estados[pos_atual].ordem, estados[nova_pos].ordem = estados[nova_pos].ordem, estados[pos_atual].ordem
            session.commit()
            self.alterado = True
        finally:
            session.close()
        self._carregar()
