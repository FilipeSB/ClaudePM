from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QCheckBox, QDialogButtonBox, QVBoxLayout,
    QPushButton, QColorDialog
)
from PySide6.QtGui import QColor
from database.db import get_session
from database.models import Pessoa, Equipa, Perfil
from ui.base_crud import BaseCrudWidget
from utils.cores import cor_da_pessoa, cor_sugerida_para_nova_pessoa, cor_texto_para


class PessoaDialog(QDialog):
    def __init__(self, parent=None, pessoa=None):
        super().__init__(parent)
        self.setWindowTitle("Pessoa")
        self.pessoa = pessoa

        session = get_session()
        try:
            self.equipas = session.query(Equipa).order_by(Equipa.nome).all()
            self.perfis = session.query(Perfil).order_by(Perfil.codigo).all()
            n_pessoas = session.query(Pessoa).count()
        finally:
            session.close()

        self.nome = QLineEdit(pessoa.nome if pessoa else "")
        self.email = QLineEdit(pessoa.email if pessoa else "")

        self.equipa_combo = QComboBox()
        self.equipa_combo.addItem("(sem equipa)", None)
        for e in self.equipas:
            self.equipa_combo.addItem(e.nome, e.id)
        if pessoa and pessoa.equipa_id:
            idx = self.equipa_combo.findData(pessoa.equipa_id)
            if idx >= 0:
                self.equipa_combo.setCurrentIndex(idx)

        self.perfil_combo = QComboBox()
        self.perfil_combo.addItem("(sem perfil)", None)
        for p in self.perfis:
            self.perfil_combo.addItem(f"{p.codigo} - {p.designacao}", p.id)
        if pessoa and pessoa.perfil_id:
            idx = self.perfil_combo.findData(pessoa.perfil_id)
            if idx >= 0:
                self.perfil_combo.setCurrentIndex(idx)

        self.ativo = QCheckBox("Ativo")
        self.ativo.setChecked(pessoa.ativo if pessoa else True)

        # Cor da pessoa: usada nas barras do Calendário e da Alocação.
        # Uma pessoa nova começa com uma cor sugerida (diferente das anteriores).
        if pessoa is not None:
            self._cor = cor_da_pessoa(pessoa.cor, pessoa.id)
        else:
            self._cor = cor_sugerida_para_nova_pessoa(n_pessoas)
        self.btn_cor = QPushButton("Escolher cor...")
        self.btn_cor.clicked.connect(self._escolher_cor)
        self._atualizar_botao_cor()

        form = QFormLayout()
        form.addRow("Nome*", self.nome)
        form.addRow("Email", self.email)
        form.addRow("Equipa", self.equipa_combo)
        form.addRow("Perfil", self.perfil_combo)
        form.addRow("Cor (calendário e alocação)", self.btn_cor)
        form.addRow("", self.ativo)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(botoes)

    def _atualizar_botao_cor(self):
        texto_cor = cor_texto_para(self._cor)
        self.btn_cor.setStyleSheet(f"background-color: {self._cor}; color: {texto_cor}; padding: 4px;")
        self.btn_cor.setText(f"Cor: {self._cor}  (clicar para mudar)")

    def _escolher_cor(self):
        nova = QColorDialog.getColor(QColor(self._cor), self, "Escolher cor da pessoa")
        if nova.isValid():
            self._cor = nova.name().upper()
            self._atualizar_botao_cor()

    def dados(self):
        return {
            "nome": self.nome.text().strip(),
            "email": self.email.text().strip(),
            "equipa_id": self.equipa_combo.currentData(),
            "perfil_id": self.perfil_combo.currentData(),
            "ativo": self.ativo.isChecked(),
            "cor": self._cor,
        }


class VistaPessoas(BaseCrudWidget):
    modelo = Pessoa

    def __init__(self):
        self.colunas = ["Nome", "Equipa", "Perfil", "Email", "Ativo", "Cor"]
        super().__init__("Pessoa")

    def carregar_linhas(self):
        session = get_session()
        try:
            pessoas = session.query(Pessoa).order_by(Pessoa.nome).all()
            return [
                (p, [
                    p.nome,
                    p.equipa.nome if p.equipa else "",
                    p.perfil.codigo if p.perfil else "",
                    p.email or "",
                    "Sim" if p.ativo else "Não",
                    cor_da_pessoa(p.cor, p.id),
                ])
                for p in pessoas
            ]
        finally:
            session.close()

    def refresh(self):
        super().refresh()
        col_cor = len(self.colunas) - 1
        for row in range(self.tabela.rowCount()):
            item = self.tabela.item(row, col_cor)
            if item is not None:
                cor = QColor(item.text())
                item.setBackground(cor)
                item.setForeground(QColor(cor_texto_para(item.text())))

    def abrir_formulario(self, obj=None):
        dialog = PessoaDialog(self, obj)
        if dialog.exec() == QDialog.Accepted:
            dados = dialog.dados()
            if not dados["nome"]:
                return

            def gravar():
                session = get_session()
                try:
                    if obj is None:
                        session.add(Pessoa(**dados))
                    else:
                        pessoa = session.get(Pessoa, obj.id)
                        for k, v in dados.items():
                            setattr(pessoa, k, v)
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()

            if self.executar_com_seguranca(gravar, "Erro ao gravar pessoa"):
                self.refresh()

    def eliminar(self, obj):
        def apagar():
            session = get_session()
            try:
                pessoa = session.get(Pessoa, obj.id)
                if pessoa:
                    session.delete(pessoa)
                    session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        self.executar_com_seguranca(apagar, "Erro ao eliminar pessoa")
