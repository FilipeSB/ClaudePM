from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QFileDialog, QMessageBox
)
from PySide6.QtGui import QAction

from database.db import fazer_backup, nome_sugerido_backup, get_session, DB_PATH
from utils.importacao import gerar_template, importar_excel

from ui.vista_clientes import VistaClientes
from ui.vista_equipas import VistaEquipas
from ui.vista_perfis import VistaPerfis
from ui.vista_pessoas import VistaPessoas
from ui.vista_projetos import VistaProjetos
from ui.vista_tarefas import VistaTarefas
from ui.vista_calendario import VistaCalendario
from ui.vista_alocacao import VistaAlocacao


class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestão de Pessoas e Projetos")
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
        self.tabs.addTab(self.vista_perfis, "Perfis (CC01-CC07)")
        self.tabs.addTab(self.vista_pessoas, "Pessoas")
        self.tabs.addTab(self.vista_projetos, "Projetos")
        self.tabs.addTab(self.vista_tarefas, "Tarefas / Atividades")
        self.tabs.addTab(self.vista_calendario, "Calendário")
        self.tabs.addTab(self.vista_alocacao, "Alocação")

        # Atualizar calendário/alocação sempre que se muda para o respetivo separador,
        # para refletir alterações feitas noutras vistas.
        self.tabs.currentChanged.connect(self._ao_mudar_separador)

        self._criar_menu()

    # ------------------------------------------------------------------
    def _criar_menu(self):
        menu_ficheiro = self.menuBar().addMenu("&Ficheiro")

        acao_backup = QAction("Fazer backup da base de dados...", self)
        acao_backup.triggered.connect(self._fazer_backup)
        menu_ficheiro.addAction(acao_backup)

        menu_ficheiro.addSeparator()

        acao_template = QAction("Descarregar template Excel...", self)
        acao_template.triggered.connect(self._descarregar_template)
        menu_ficheiro.addAction(acao_template)

        acao_importar = QAction("Importar dados de Excel...", self)
        acao_importar.triggered.connect(self._importar_excel)
        menu_ficheiro.addAction(acao_importar)

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

    def _importar_excel(self):
        origem, _ = QFileDialog.getOpenFileName(
            self, "Selecionar ficheiro Excel a importar", "", "Ficheiros Excel (*.xlsx)"
        )
        if not origem:
            return

        resp = QMessageBox.question(
            self, "Confirmar importação",
            "A importação vai criar novos registos e ATUALIZAR os já existentes "
            "com o mesmo nome/código. Recomenda-se fazer um backup antes.\n\n"
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

    # ------------------------------------------------------------------
    def _atualizar_todas_as_vistas(self):
        for vista in (
            self.vista_clientes, self.vista_equipas, self.vista_perfis,
            self.vista_pessoas, self.vista_projetos, self.vista_tarefas,
        ):
            vista.refresh()
        self.vista_calendario.refresh_filtros()
        self.vista_alocacao.refresh_filtros()

    def _ao_mudar_separador(self, index):
        widget = self.tabs.widget(index)
        if widget is self.vista_calendario:
            self.vista_calendario.refresh_filtros()
        elif widget is self.vista_alocacao:
            self.vista_alocacao.refresh_filtros()
