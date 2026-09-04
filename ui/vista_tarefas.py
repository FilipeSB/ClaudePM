from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QDateEdit, QDialogButtonBox,
    QVBoxLayout, QHBoxLayout, QMessageBox, QTableWidget, QTableWidgetItem,
    QPushButton, QDoubleSpinBox, QWidget, QHeaderView, QAbstractItemView, QLabel
)
from PySide6.QtCore import QDate
from database.db import get_session
from database.models import Tarefa, Projeto, Pessoa, Alocacao, ESTADOS_TAREFA
from ui.base_crud import BaseCrudWidget
from ui.vista_projetos import qdate_to_pydate, pydate_to_qdate


def sobreposicao_datas(inicio1, fim1, inicio2, fim2):
    if not all([inicio1, fim1, inicio2, fim2]):
        return False
    return inicio1 <= fim2 and inicio2 <= fim1


def verificar_sobrealocacoes(session, tarefa_id, data_inicio, data_fim, alocacoes_novas):
    """
    Para cada (pessoa_id, percentagem) da tarefa em edição, soma as percentagens
    de OUTRAS tarefas dessa pessoa cujo período se sobreponha ao da tarefa atual,
    e verifica se, somado à nova percentagem, ultrapassa 100%.

    Retorna lista de strings descrevendo os conflitos encontrados (vazia se OK).
    """
    conflitos = []
    for pessoa_id, pct_nova in alocacoes_novas:
        pessoa = session.get(Pessoa, pessoa_id)
        if not pessoa:
            continue

        total_outras = 0.0
        for a in pessoa.alocacoes:
            if a.tarefa_id == tarefa_id:
                continue  # ignora alocações da própria tarefa (serão substituídas)
            t = a.tarefa
            if not t:
                continue
            if sobreposicao_datas(data_inicio, data_fim, t.data_inicio, t.data_fim):
                total_outras += float(a.percentagem or 0)

        total = total_outras + pct_nova
        if total > 100:
            conflitos.append(
                f"{pessoa.nome}: {total:.0f}% no total ({total_outras:.0f}% noutras tarefas "
                f"sobrepostas + {pct_nova:.0f}% nesta tarefa)"
            )
    return conflitos


class AlocacaoRowWidget(QWidget):
    """Uma linha de alocação: combo de pessoa + percentagem."""

    def __init__(self, pessoas, pessoa_id=None, percentagem=0):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.pessoa_combo = QComboBox()
        for p in pessoas:
            self.pessoa_combo.addItem(p.nome, p.id)
        if pessoa_id:
            idx = self.pessoa_combo.findData(pessoa_id)
            if idx >= 0:
                self.pessoa_combo.setCurrentIndex(idx)

        self.percentagem_spin = QDoubleSpinBox()
        self.percentagem_spin.setRange(0, 100)
        self.percentagem_spin.setSuffix(" %")
        self.percentagem_spin.setValue(float(percentagem))

        layout.addWidget(self.pessoa_combo, 3)
        layout.addWidget(self.percentagem_spin, 1)

    def dados(self):
        return self.pessoa_combo.currentData(), self.percentagem_spin.value()


class TarefaDialog(QDialog):
    def __init__(self, parent=None, tarefa=None):
        super().__init__(parent)
        self.setWindowTitle("Tarefa / Atividade")
        self.tarefa = tarefa
        self.resize(480, 500)

        session = get_session()
        try:
            self.projetos = session.query(Projeto).order_by(Projeto.nome).all()
            self.pessoas = session.query(Pessoa).filter_by(ativo=True).order_by(Pessoa.nome).all()
            alocacoes_existentes = []
            if tarefa:
                alocacoes_existentes = [(a.pessoa_id, float(a.percentagem or 0)) for a in tarefa.alocacoes]
        finally:
            session.close()

        self.nome = QLineEdit(tarefa.nome if tarefa else "")

        self.projeto_combo = QComboBox()
        self.projeto_combo.addItem("(sem projeto)", None)
        for p in self.projetos:
            self.projeto_combo.addItem(p.nome, p.id)
        if tarefa and tarefa.projeto_id:
            idx = self.projeto_combo.findData(tarefa.projeto_id)
            if idx >= 0:
                self.projeto_combo.setCurrentIndex(idx)

        self.data_inicio = QDateEdit(calendarPopup=True)
        self.data_inicio.setDate(pydate_to_qdate(tarefa.data_inicio if tarefa else None))
        self.data_fim = QDateEdit(calendarPopup=True)
        self.data_fim.setDate(pydate_to_qdate(tarefa.data_fim if tarefa else None))

        self.estado_combo = QComboBox()
        self.estado_combo.addItems(ESTADOS_TAREFA)
        if tarefa and tarefa.estado in ESTADOS_TAREFA:
            self.estado_combo.setCurrentText(tarefa.estado)

        form = QFormLayout()
        form.addRow("Nome*", self.nome)
        form.addRow("Projeto", self.projeto_combo)
        form.addRow("Data início", self.data_inicio)
        form.addRow("Data fim", self.data_fim)
        form.addRow("Estado", self.estado_combo)

        # --- Alocações de pessoas ---
        self.alocacoes_container = QVBoxLayout()
        self.linhas_alocacao = []

        btn_add = QPushButton("+ Adicionar pessoa")
        btn_add.clicked.connect(self._adicionar_linha_alocacao)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self._validar_e_aceitar)
        botoes.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Pessoas alocadas e percentagem:"))
        layout.addLayout(self.alocacoes_container)
        layout.addWidget(btn_add)
        layout.addWidget(botoes)

        if not self.pessoas:
            btn_add.setEnabled(False)
        else:
            if alocacoes_existentes:
                for pessoa_id, pct in alocacoes_existentes:
                    self._adicionar_linha_alocacao(pessoa_id, pct)
            else:
                self._adicionar_linha_alocacao()

    def _adicionar_linha_alocacao(self, pessoa_id=None, percentagem=0):
        linha = AlocacaoRowWidget(self.pessoas, pessoa_id, percentagem)
        self.alocacoes_container.addWidget(linha)
        self.linhas_alocacao.append(linha)

    def _validar_e_aceitar(self):
        if self.data_fim.date() < self.data_inicio.date():
            QMessageBox.warning(self, "Datas inválidas", "A data de fim não pode ser anterior à data de início.")
            return
        self.accept()

    def dados(self):
        return {
            "nome": self.nome.text().strip(),
            "projeto_id": self.projeto_combo.currentData(),
            "data_inicio": qdate_to_pydate(self.data_inicio.date()),
            "data_fim": qdate_to_pydate(self.data_fim.date()),
            "estado": self.estado_combo.currentText(),
        }

    def alocacoes(self):
        """Retorna lista de (pessoa_id, percentagem), ignorando linhas sem pessoa."""
        resultado = []
        for linha in self.linhas_alocacao:
            pessoa_id, pct = linha.dados()
            if pessoa_id is not None and pct > 0:
                resultado.append((pessoa_id, pct))
        return resultado


class VistaTarefas(BaseCrudWidget):
    def __init__(self):
        self.colunas = ["ID", "Nome", "Projeto", "Início", "Fim", "Estado", "Pessoas Alocadas"]
        super().__init__("Tarefa")

    def carregar_linhas(self):
        session = get_session()
        try:
            tarefas = session.query(Tarefa).order_by(Tarefa.data_inicio.desc()).all()
            linhas = []
            for t in tarefas:
                pessoas_txt = ", ".join(
                    f"{a.pessoa.nome} ({a.percentagem}%)" for a in t.alocacoes if a.pessoa
                )
                linhas.append((t, [
                    t.id, t.nome,
                    t.projeto.nome if t.projeto else "",
                    t.data_inicio, t.data_fim, t.estado, pessoas_txt,
                ]))
            return linhas
        finally:
            session.close()

    def abrir_formulario(self, obj=None):
        dialog = TarefaDialog(self, obj)
        if dialog.exec() == QDialog.Accepted:
            dados = dialog.dados()
            if not dados["nome"]:
                return
            alocacoes = dialog.alocacoes()

            session = get_session()
            try:
                conflitos = verificar_sobrealocacoes(
                    session,
                    tarefa_id=obj.id if obj else None,
                    data_inicio=dados["data_inicio"],
                    data_fim=dados["data_fim"],
                    alocacoes_novas=alocacoes,
                )
            finally:
                session.close()

            if conflitos:
                resp = QMessageBox.warning(
                    self, "Sobre-alocação detetada",
                    "As seguintes pessoas ficariam alocadas acima de 100% em período sobreposto:\n\n"
                    + "\n".join(conflitos)
                    + "\n\nQueres gravar mesmo assim?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if resp != QMessageBox.Yes:
                    return

            session = get_session()
            try:
                if obj is None:
                    tarefa = Tarefa(**dados)
                    session.add(tarefa)
                    session.flush()
                else:
                    tarefa = session.get(Tarefa, obj.id)
                    for k, v in dados.items():
                        setattr(tarefa, k, v)
                    # remove alocações antigas para recriar
                    for a in list(tarefa.alocacoes):
                        session.delete(a)
                    session.flush()

                for pessoa_id, pct in alocacoes:
                    session.add(Alocacao(tarefa_id=tarefa.id, pessoa_id=pessoa_id, percentagem=pct))

                session.commit()
            finally:
                session.close()
            self.refresh()

    def eliminar(self, obj):
        session = get_session()
        try:
            tarefa = session.get(Tarefa, obj.id)
            if tarefa:
                session.delete(tarefa)
                session.commit()
        finally:
            session.close()
