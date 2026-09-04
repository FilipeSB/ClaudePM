from PySide6.QtWidgets import QMainWindow, QTabWidget

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
        self.resize(1200, 750)

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        self.vista_clientes = VistaClientes()
        self.vista_equipas = VistaEquipas()
        self.vista_perfis = VistaPerfis()
        self.vista_pessoas = VistaPessoas()
        self.vista_projetos = VistaProjetos()
        self.vista_tarefas = VistaTarefas()
        self.vista_calendario = VistaCalendario()
        self.vista_alocacao = VistaAlocacao()

        tabs.addTab(self.vista_clientes, "Clientes")
        tabs.addTab(self.vista_equipas, "Equipas")
        tabs.addTab(self.vista_perfis, "Perfis (CC01-CC07)")
        tabs.addTab(self.vista_pessoas, "Pessoas")
        tabs.addTab(self.vista_projetos, "Projetos")
        tabs.addTab(self.vista_tarefas, "Tarefas / Atividades")
        tabs.addTab(self.vista_calendario, "Calendário")
        tabs.addTab(self.vista_alocacao, "Alocação")

        # Atualizar calendário/alocação sempre que se muda para o respetivo separador,
        # para refletir alterações feitas noutras vistas.
        tabs.currentChanged.connect(self._ao_mudar_separador)

    def _ao_mudar_separador(self, index):
        widget = self.centralWidget().widget(index)
        if widget is self.vista_calendario:
            self.vista_calendario.refresh_filtros()
        elif widget is self.vista_alocacao:
            self.vista_alocacao.refresh()
