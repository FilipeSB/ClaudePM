from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QDateEdit, QDialogButtonBox,
    QVBoxLayout, QHBoxLayout, QMessageBox, QPushButton, QDoubleSpinBox,
    QWidget, QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import QTimer
from sqlalchemy.orm import selectinload
from database.db import get_session, listar_estados_tarefa
from database.models import Tarefa, Projeto, Pessoa, Alocacao, CATEGORIA_LABELS
from ui.base_crud import BaseCrudWidget
from ui.vista_projetos import qdate_to_pydate, pydate_to_qdate
from utils.calculos import horas_para_percentagem, percentagem_para_horas, horas_base_por_dia
from utils.formatacao import fmt_pct


def sobreposicao_datas(inicio1, fim1, inicio2, fim2):
    if not all([inicio1, fim1, inicio2, fim2]):
        return False
    return inicio1 <= fim2 and inicio2 <= fim1


def verificar_sobrealocacoes(session, tarefa_id, data_inicio, data_fim, alocacoes_novas):
    """
    Para cada (pessoa_id, percentagem, ...) da atividade em edição, soma as
    percentagens de OUTRAS atividades dessa pessoa com período sobreposto e
    verifica se, somado à nova percentagem, ultrapassa 100%.
    Retorna lista de textos com os conflitos (vazia se estiver tudo bem).
    """
    conflitos = []
    for pessoa_id, pct_nova, *_ in alocacoes_novas:
        pessoa = session.get(Pessoa, pessoa_id)
        if not pessoa:
            continue

        total_outras = 0.0
        for a in pessoa.alocacoes:
            if a.tarefa_id == tarefa_id:
                continue  # ignora alocações da própria atividade (serão substituídas)
            t = a.tarefa
            if not t:
                continue
            if sobreposicao_datas(data_inicio, data_fim, t.data_inicio, t.data_fim):
                total_outras += float(a.percentagem or 0)

        total = total_outras + pct_nova
        if total > 100:
            conflitos.append(
                f"{pessoa.nome}: {fmt_pct(total)} no total ({fmt_pct(total_outras)} noutras atividades "
                f"sobrepostas + {fmt_pct(pct_nova)} nesta atividade)"
            )
    return conflitos


class AlocacaoRowWidget(QWidget):
    """Uma linha de alocação: pessoa + tipo (%/horas) + valor + categoria + remover."""

    def __init__(self, pessoas, pessoa_id=None, percentagem=0, tipo="percentagem",
                 horas=None, categoria="8h_uteis", ao_remover=None):
        """pessoas: lista de tuplos (id, texto_a_mostrar)."""
        super().__init__()
        self._ao_remover = ao_remover

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.pessoa_combo = QComboBox()
        for pid, texto in pessoas:
            self.pessoa_combo.addItem(texto, pid)
        if pessoa_id:
            idx = self.pessoa_combo.findData(pessoa_id)
            if idx >= 0:
                self.pessoa_combo.setCurrentIndex(idx)

        self.tipo_combo = QComboBox()
        self.tipo_combo.addItem("Percentagem", "percentagem")
        self.tipo_combo.addItem("Horas", "horas")
        idx_tipo = self.tipo_combo.findData(tipo)
        if idx_tipo >= 0:
            self.tipo_combo.setCurrentIndex(idx_tipo)

        self.categoria_combo = QComboBox()
        for chave, label in CATEGORIA_LABELS.items():
            self.categoria_combo.addItem(label, chave)
        idx_cat = self.categoria_combo.findData(categoria)
        if idx_cat >= 0:
            self.categoria_combo.setCurrentIndex(idx_cat)

        self.valor_spin = QDoubleSpinBox()
        self.valor_spin.setDecimals(1)
        self._configurar_valor_spin(percentagem, horas, tipo, categoria)

        self.btn_remover = QPushButton("✕")
        self.btn_remover.setFixedWidth(28)
        self.btn_remover.setToolTip("Remover esta pessoa da atividade")
        self.btn_remover.clicked.connect(self._remover)

        layout.addWidget(self.pessoa_combo, 3)
        layout.addWidget(self.tipo_combo, 2)
        layout.addWidget(self.valor_spin, 2)
        layout.addWidget(self.categoria_combo, 3)
        layout.addWidget(self.btn_remover)

        self.tipo_combo.currentIndexChanged.connect(self._ao_mudar_tipo_ou_categoria)
        self.categoria_combo.currentIndexChanged.connect(self._ao_mudar_tipo_ou_categoria)

    def _configurar_valor_spin(self, percentagem, horas, tipo, categoria):
        if tipo == "horas":
            base = horas_base_por_dia(categoria)
            self.valor_spin.setRange(0, base)
            self.valor_spin.setSuffix(" h")
            self.valor_spin.setValue(float(horas) if horas is not None else percentagem_para_horas(percentagem, categoria))
        else:
            self.valor_spin.setRange(0, 100)
            self.valor_spin.setSuffix(" %")
            self.valor_spin.setValue(float(percentagem or 0))

    def _ao_mudar_tipo_ou_categoria(self):
        tipo = self.tipo_combo.currentData()
        categoria = self.categoria_combo.currentData()
        if tipo == "horas":
            self.valor_spin.setRange(0, horas_base_por_dia(categoria))
            self.valor_spin.setSuffix(" h")
        else:
            self.valor_spin.setRange(0, 100)
            self.valor_spin.setSuffix(" %")

    def _remover(self):
        # Remoção diferida: destruir este widget de dentro do handler de
        # clique do seu próprio botão é instável em Qt (causa de fechos
        # inesperados). Diferir para a iteração seguinte do event loop evita-o.
        QTimer.singleShot(0, self._remover_efetivo)

    def _remover_efetivo(self):
        if self._ao_remover:
            self._ao_remover(self)
        pai = self.parentWidget()
        if pai is not None and pai.layout() is not None:
            pai.layout().removeWidget(self)
        self.hide()
        self.deleteLater()

    def dados(self):
        """Retorna (pessoa_id, percentagem, tipo, horas, categoria)."""
        pessoa_id = self.pessoa_combo.currentData()
        tipo = self.tipo_combo.currentData()
        categoria = self.categoria_combo.currentData()
        valor = self.valor_spin.value()
        if tipo == "horas":
            horas = valor
            percentagem = horas_para_percentagem(horas, categoria)
        else:
            horas = None
            percentagem = valor
        return pessoa_id, percentagem, tipo, horas, categoria


class TarefaDialog(QDialog):
    def __init__(self, parent=None, tarefa=None):
        super().__init__(parent)
        self.setWindowTitle("Atividade")
        self.tarefa = tarefa
        self.resize(620, 600)

        # Todos os dados necessários são lidos aqui, dentro da sessão, para
        # guardar apenas valores simples (nunca objetos ligados à base de dados).
        session = get_session()
        try:
            projetos = session.query(Projeto).options(selectinload(Projeto.cliente)).order_by(Projeto.nome).all()
            self._info_projetos = [
                (p.id, p.nome, p.cliente.nome if p.cliente else "", p.data_inicio, p.data_fim)
                for p in projetos
            ]
            pessoas_ativas = session.query(Pessoa).filter_by(ativo=True).order_by(Pessoa.nome).all()
            self.estados_disponiveis = listar_estados_tarefa(session)

            alocacoes_existentes = []
            pessoas_extra = []
            if tarefa is not None and getattr(tarefa, "id", None):
                alocs = session.query(Alocacao).filter_by(tarefa_id=tarefa.id).all()
                alocacoes_existentes = [
                    (a.pessoa_id, float(a.percentagem or 0), a.tipo or "percentagem",
                     float(a.horas) if a.horas is not None else None, a.categoria or "8h_uteis")
                    for a in alocs
                ]
                ativos_ids = {p.id for p in pessoas_ativas}
                extra_ids = {a[0] for a in alocacoes_existentes} - ativos_ids
                if extra_ids:
                    # pessoas já alocadas mas entretanto marcadas como inativas:
                    # mantêm-se na lista para não perder/trocar a alocação
                    pessoas_extra = session.query(Pessoa).filter(Pessoa.id.in_(extra_ids)).all()
            self.pessoas = (
                [(p.id, p.nome) for p in pessoas_ativas]
                + [(p.id, f"{p.nome} (inativo)") for p in pessoas_extra]
            )
        finally:
            session.close()

        self._datas_projetos = {i: (ini, fim) for i, _n, _c, ini, fim in self._info_projetos}
        self._cliente_do_projeto = {i: c for i, _n, c, _ini, _fim in self._info_projetos}

        self.nome = QLineEdit(tarefa.nome if tarefa else "")

        # Na lista de projetos mostra-se também o cliente a que pertencem
        self.projeto_combo = QComboBox()
        self.projeto_combo.addItem("(sem projeto)", None)
        for pid, pnome, cliente, _ini, _fim in self._info_projetos:
            texto = f"{pnome}   —   Cliente: {cliente}" if cliente else f"{pnome}   —   (sem cliente)"
            self.projeto_combo.addItem(texto, pid)
        if tarefa and tarefa.projeto_id:
            idx = self.projeto_combo.findData(tarefa.projeto_id)
            if idx >= 0:
                self.projeto_combo.setCurrentIndex(idx)

        self.label_cliente = QLabel("")
        self.label_cliente.setStyleSheet("font-weight: bold;")
        self.projeto_combo.currentIndexChanged.connect(self._atualizar_label_cliente)
        self._atualizar_label_cliente()

        self.data_inicio = QDateEdit(calendarPopup=True)
        self.data_inicio.setDate(pydate_to_qdate(tarefa.data_inicio if tarefa else None))
        self.data_fim = QDateEdit(calendarPopup=True)
        self.data_fim.setDate(pydate_to_qdate(tarefa.data_fim if tarefa else None))

        # Ao escolher (ativamente) um projeto, as datas passam a ter por
        # defeito as datas do projeto -- mas continuam editáveis à mão depois.
        self.projeto_combo.activated.connect(self._preencher_datas_do_projeto)

        self.estado_combo = QComboBox()
        self.estado_combo.addItems(self.estados_disponiveis)
        if tarefa and tarefa.estado:
            if tarefa.estado not in self.estados_disponiveis:
                self.estado_combo.addItem(tarefa.estado)
            self.estado_combo.setCurrentText(tarefa.estado)

        form = QFormLayout()
        form.addRow("Nome*", self.nome)
        form.addRow("Projeto", self.projeto_combo)
        form.addRow("Cliente do projeto", self.label_cliente)
        form.addRow("Data início", self.data_inicio)
        form.addRow("Data fim", self.data_fim)
        form.addRow("Estado", self.estado_combo)

        # --- Alocações de pessoas ---
        self.alocacoes_container = QVBoxLayout()
        self.linhas_alocacao = []

        cabecalho = QHBoxLayout()
        for texto, largura in [("Pessoa", 3), ("Tipo", 2), ("Valor", 2), ("Categoria", 3), ("", 1)]:
            lbl = QLabel(texto)
            lbl.setStyleSheet("font-weight: bold; color: #555;")
            cabecalho.addWidget(lbl, largura)

        btn_add = QPushButton("+ Adicionar pessoa")
        btn_add.clicked.connect(lambda: self._adicionar_linha_alocacao())

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self._validar_e_aceitar)
        botoes.rejected.connect(self.reject)

        self._area_alocacoes = QFrame()
        self._area_alocacoes.setLayout(self.alocacoes_container)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._area_alocacoes)
        scroll.setMinimumHeight(160)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Pessoas alocadas:"))
        layout.addLayout(cabecalho)
        layout.addWidget(scroll)
        layout.addWidget(btn_add)
        layout.addWidget(botoes)

        if not self.pessoas:
            btn_add.setEnabled(False)
        elif alocacoes_existentes:
            for pessoa_id, pct, tipo, horas, categoria in alocacoes_existentes:
                self._adicionar_linha_alocacao(pessoa_id, pct, tipo, horas, categoria)
        else:
            self._adicionar_linha_alocacao()

    def _atualizar_label_cliente(self, _index=None):
        projeto_id = self.projeto_combo.currentData()
        if projeto_id is None:
            self.label_cliente.setText("—")
        else:
            self.label_cliente.setText(self._cliente_do_projeto.get(projeto_id) or "(projeto sem cliente)")

    def _preencher_datas_do_projeto(self, _index=None):
        datas = self._datas_projetos.get(self.projeto_combo.currentData())
        if datas and datas[0] and datas[1]:
            self.data_inicio.setDate(pydate_to_qdate(datas[0]))
            self.data_fim.setDate(pydate_to_qdate(datas[1]))

    def _adicionar_linha_alocacao(self, pessoa_id=None, percentagem=0, tipo="percentagem",
                                   horas=None, categoria="8h_uteis"):
        linha = AlocacaoRowWidget(
            self.pessoas, pessoa_id, percentagem, tipo, horas, categoria,
            ao_remover=self._remover_linha_alocacao,
        )
        self.alocacoes_container.addWidget(linha)
        self.linhas_alocacao.append(linha)

    def _remover_linha_alocacao(self, linha):
        if linha in self.linhas_alocacao:
            self.linhas_alocacao.remove(linha)

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
        """Lista de (pessoa_id, percentagem, tipo, horas, categoria), ignorando linhas vazias."""
        resultado = []
        for linha in self.linhas_alocacao:
            pessoa_id, pct, tipo, horas, categoria = linha.dados()
            if pessoa_id is not None and pct > 0:
                resultado.append((pessoa_id, pct, tipo, horas, categoria))
        return resultado


class VistaTarefas(BaseCrudWidget):
    modelo = Tarefa

    def __init__(self):
        self.colunas = ["Cliente", "Projeto", "Nome", "Início", "Fim", "Estado", "Pessoas Alocadas"]
        super().__init__("Atividade")

    def carregar_linhas(self):
        session = get_session()
        try:
            tarefas = (
                session.query(Tarefa)
                .options(
                    selectinload(Tarefa.alocacoes).selectinload(Alocacao.pessoa),
                    selectinload(Tarefa.projeto).selectinload(Projeto.cliente),
                )
                .order_by(Tarefa.data_inicio.desc())
                .all()
            )
            linhas = []
            for t in tarefas:
                pessoas_txt = ", ".join(
                    f"{a.pessoa.nome} ({fmt_pct(a.percentagem)})" for a in t.alocacoes if a.pessoa
                )
                cliente = t.projeto.cliente.nome if (t.projeto and t.projeto.cliente) else ""
                linhas.append((t, [
                    cliente,
                    t.projeto.nome if t.projeto else "",
                    t.nome, t.data_inicio, t.data_fim, t.estado, pessoas_txt,
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

            try:
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

                    for pessoa_id, pct, tipo, horas, categoria in alocacoes:
                        session.add(Alocacao(
                            tarefa_id=tarefa.id, pessoa_id=pessoa_id, percentagem=pct,
                            tipo=tipo, horas=horas, categoria=categoria,
                        ))

                    session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()
            except Exception as exc:
                QMessageBox.critical(self, "Erro ao gravar atividade", f"Não foi possível gravar:\n\n{exc}")
                return
            self.refresh()

    def eliminar(self, obj):
        try:
            session = get_session()
            try:
                tarefa = session.get(Tarefa, obj.id)
                if tarefa:
                    session.delete(tarefa)
                    session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao eliminar", f"Não foi possível eliminar:\n\n{exc}")
