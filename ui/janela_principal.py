from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QFileDialog, QMessageBox
)
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtCore import QUrl

from database.db import fazer_backup, nome_sugerido_backup, restaurar_backup, get_session, DB_PATH, PASTA_DADOS
from database.models import EstadoProjeto, EstadoTarefa, Projeto, Tarefa
from utils.importacao import gerar_template, importar_excel, exportar_dados_atuais
from utils.versao import VERSAO

from ui.vista_clientes import VistaClientes
from ui.vista_equipas import VistaEquipas
from ui.vista_perfis import VistaPerfis
from ui.vista_pessoas import VistaPessoas
from ui.vista_projetos import VistaProjetos
from ui.vista_tarefas import VistaTarefas
from ui.vista_calendario import VistaCalendario
from ui.vista_alocacao import VistaAlocacao
from ui.gerir_estados_dialog import GerirEstadosDialog
from ui.gerir_feriados_dialog import GerirFeriadosDialog


class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Gestão de Pessoas e Projetos — v{VERSAO}")
        self.resize(1300, 780)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.vista_clientes = VistaClientes()
        self.vista_equipas = VistaEquipas()
        self.vista_perfis = VistaPerfis()
        self.vista_pessoas = VistaPessoas()
        self.vista_projetos = VistaProjetos()
        self.vista_tarefas = VistaTarefas()
        self.vista_calendario = VistaCalendario()
        self.vista_alocacao = VistaAlocacao()

        self.tabs.addTab(self.vista_clientes, "Clientes")
        self.tabs.addTab(self.vista_equipas, "Equipas")
        self.tabs.addTab(self.vista_perfis, "Perfis")
        self.tabs.addTab(self.vista_pessoas, "Pessoas")
        self.tabs.addTab(self.vista_projetos, "Projetos")
        self.tabs.addTab(self.vista_tarefas, "Atividades")
        self.tabs.addTab(self.vista_calendario, "Calendário")
        self.tabs.addTab(self.vista_alocacao, "Alocação")

        # Atualizar calendário/alocação sempre que se muda para o respetivo separador,
        # para refletir alterações feitas noutras vistas.
        self.tabs.currentChanged.connect(self._ao_mudar_separador)

        # O calendário abre as janelas de edição das outras vistas
        self.vista_calendario.definir_editores({
            'cliente': self.vista_clientes.editar_por_id,
            'projeto': self.vista_projetos.editar_por_id,
            'tarefa': self.vista_tarefas.editar_por_id,
            'pessoa': self.vista_pessoas.editar_por_id,
        })

        self._criar_menu()

    # ------------------------------------------------------------------
    def _criar_menu(self):
        menu_ficheiro = self.menuBar().addMenu("&Ficheiro")

        acao_backup = QAction("Fazer backup da base de dados...", self)
        acao_backup.triggered.connect(self._fazer_backup)
        menu_ficheiro.addAction(acao_backup)

        acao_restaurar = QAction("Restaurar base de dados a partir de backup...", self)
        acao_restaurar.triggered.connect(self._restaurar_backup)
        menu_ficheiro.addAction(acao_restaurar)

        menu_ficheiro.addSeparator()

        acao_template = QAction("Descarregar template Excel (em branco)...", self)
        acao_template.triggered.connect(self._descarregar_template)
        menu_ficheiro.addAction(acao_template)

        acao_exportar_dados = QAction("Exportar dados atuais para Excel...", self)
        acao_exportar_dados.triggered.connect(self._exportar_dados_atuais)
        menu_ficheiro.addAction(acao_exportar_dados)

        acao_importar = QAction("Importar dados de Excel...", self)
        acao_importar.triggered.connect(self._importar_excel)
        menu_ficheiro.addAction(acao_importar)

        menu_config = self.menuBar().addMenu("&Configurações")

        acao_estados_projeto = QAction("Estados de Projetos...", self)
        acao_estados_projeto.triggered.connect(self._gerir_estados_projeto)
        menu_config.addAction(acao_estados_projeto)

        acao_estados_tarefa = QAction("Estados de Atividades...", self)
        acao_estados_tarefa.triggered.connect(self._gerir_estados_tarefa)
        menu_config.addAction(acao_estados_tarefa)

        menu_config.addSeparator()

        acao_feriados = QAction("Feriados...", self)
        acao_feriados.triggered.connect(self._gerir_feriados)
        menu_config.addAction(acao_feriados)

        # O menu Ajuda fica sempre o mais à direita, por isso é o último a ser criado.
        menu_ajuda = self.menuBar().addMenu("&Ajuda")
        acao_pasta = QAction("Abrir pasta de dados e registo de erros...", self)
        acao_pasta.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(PASTA_DADOS)))
        menu_ajuda.addAction(acao_pasta)
        acao_sobre = QAction("Sobre...", self)
        acao_sobre.triggered.connect(lambda: QMessageBox.information(
            self, "Sobre", f"Gestão de Pessoas e Projetos\nVersão {VERSAO}\n\nDados em:\n{PASTA_DADOS}"))
        menu_ajuda.addAction(acao_sobre)

    # ------------------------------------------------------------------
    def _fazer_backup(self):
        destino, _ = QFileDialog.getSaveFileName(
            self, "Guardar backup da base de dados",
            nome_sugerido_backup(), "Base de dados (*.db)"
        )
        if not destino:
            return
        try:
            fazer_backup(destino)
            QMessageBox.information(self, "Backup concluído", f"Backup guardado em:\n{destino}")
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao fazer backup", str(exc))

    def _descarregar_template(self):
        destino, _ = QFileDialog.getSaveFileName(
            self, "Guardar template Excel",
            "template_importacao.xlsx", "Ficheiros Excel (*.xlsx)"
        )
        if not destino:
            return
        try:
            gerar_template(destino)
            QMessageBox.information(
                self, "Template gerado",
                f"Template guardado em:\n{destino}\n\n"
                "Preenche os dados nas várias folhas e depois usa "
                "'Ficheiro > Importar dados de Excel...' para os carregar."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao gerar template", str(exc))

    def _exportar_dados_atuais(self):
        destino, _ = QFileDialog.getSaveFileName(
            self, "Exportar dados atuais para Excel",
            "dados_atuais.xlsx", "Ficheiros Excel (*.xlsx)"
        )
        if not destino:
            return
        session = get_session()
        try:
            exportar_dados_atuais(destino, session)
            QMessageBox.information(
                self, "Exportação concluída",
                f"Todos os dados atuais foram exportados para:\n{destino}\n\n"
                "Podes editar este ficheiro (alterar linhas existentes, mantendo o "
                "ID, ou acrescentar linhas novas sem ID) e depois importá-lo de "
                "volta em 'Ficheiro > Importar dados de Excel...'."
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
        finally:
            session.close()

    def _importar_excel(self):
        origem, _ = QFileDialog.getOpenFileName(
            self, "Selecionar ficheiro Excel a importar", "", "Ficheiros Excel (*.xlsx)"
        )
        if not origem:
            return

        resp = QMessageBox.question(
            self, "Confirmar importação",
            "A importação vai criar novos registos e ATUALIZAR os já existentes "
            "(por ID, se o ficheiro tiver essa coluna, ou por nome/código). "
            "Recomenda-se fazer um backup antes.\n\n"
            "Continuar com a importação?"
        )
        if resp != QMessageBox.Yes:
            return

        session = get_session()
        try:
            resumo, avisos = importar_excel(origem, session)
        except Exception as exc:
            session.rollback()
            QMessageBox.critical(self, "Erro ao importar", str(exc))
            return
        finally:
            session.close()

        texto_resumo = "\n".join(f"- {k}: {v} registo(s)" for k, v in resumo.items() if v)
        mensagem = f"Importação concluída:\n\n{texto_resumo or '(nenhum registo importado)'}"
        if avisos:
            mensagem += "\n\nAvisos:\n" + "\n".join(f"- {a}" for a in avisos)
            QMessageBox.warning(self, "Importação concluída com avisos", mensagem)
        else:
            QMessageBox.information(self, "Importação concluída", mensagem)

        self._atualizar_todas_as_vistas()

    def _restaurar_backup(self):
        origem, _ = QFileDialog.getOpenFileName(
            self, "Selecionar ficheiro de backup a restaurar", "", "Base de dados (*.db)"
        )
        if not origem:
            return

        resp = QMessageBox.warning(
            self, "Confirmar restauro",
            "Isto vai SUBSTITUIR todos os dados atuais pelos do backup selecionado.\n\n"
            "O estado atual será guardado automaticamente numa cópia de segurança "
            "antes de o substituir, mas esta ação não deve ser feita de ânimo leve.\n\n"
            "Tens a certeza que queres continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        try:
            copia_seguranca = restaurar_backup(origem)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao restaurar", str(exc))
            return

        self._atualizar_todas_as_vistas()
        QMessageBox.information(
            self, "Restauro concluído",
            f"Base de dados restaurada a partir de:\n{origem}\n\n"
            f"O estado anterior foi guardado em:\n{copia_seguranca}"
        )

    # ------------------------------------------------------------------
    def _gerir_estados_projeto(self):
        def contar_uso(session, nome):
            return session.query(Projeto).filter_by(estado=nome).count()

        dialog = GerirEstadosDialog(self, "Estados de Projetos", EstadoProjeto, contar_uso, get_session)
        dialog.exec()
        if dialog.alterado:
            self.vista_calendario.refresh_filtros()
            self.vista_alocacao.refresh_filtros()

    def _gerir_estados_tarefa(self):
        def contar_uso(session, nome):
            return session.query(Tarefa).filter_by(estado=nome).count()

        dialog = GerirEstadosDialog(self, "Estados de Atividades", EstadoTarefa, contar_uso, get_session)
        dialog.exec()
        if dialog.alterado:
            self.vista_calendario.refresh_filtros()
            self.vista_alocacao.refresh_filtros()

    def _gerir_feriados(self):
        dialog = GerirFeriadosDialog(self)
        dialog.exec()
        if dialog.alterado:
            self.vista_calendario.refresh_filtros()

    # ------------------------------------------------------------------
    def _atualizar_todas_as_vistas(self):
        for vista in (
            self.vista_clientes, self.vista_equipas, self.vista_perfis,
            self.vista_pessoas, self.vista_projetos, self.vista_tarefas,
        ):
            # as vistas com filtros próprios (Projetos, Atividades) também
            # têm de repovoar os filtros, não só recarregar a tabela
            if hasattr(vista, "refresh_filtros"):
                vista.refresh_filtros()
            else:
                vista.refresh()
        self.vista_calendario.refresh_filtros()
        self.vista_alocacao.refresh_filtros()

    def _ao_mudar_separador(self, index):
        # Ao mudar de separador, a vista mostrada é sempre atualizada (as
        # alterações feitas noutra vista, ex: no Calendário, ficam logo visíveis).
        widget = self.tabs.widget(index)
        if hasattr(widget, 'refresh_filtros'):
            widget.refresh_filtros()
        elif hasattr(widget, 'refresh'):
            widget.refresh()
