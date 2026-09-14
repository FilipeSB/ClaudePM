"""
Widget reutilizável: um botão tipo dropdown que abre um menu com checkboxes,
permitindo selecionar vários valores em simultâneo (ex: vários estados).
"""
from PySide6.QtWidgets import QToolButton, QMenu, QWidgetAction, QCheckBox
from PySide6.QtCore import Signal, Qt


class FiltroMultiSelecao(QToolButton):
    alteracao = Signal()

    def __init__(self, opcoes, rotulo_todos="Todos", parent=None):
        """
        opcoes: lista de tuplos (valor, texto_visivel).
        Por defeito, todas as opções ficam selecionadas (equivalente a "sem filtro").
        """
        super().__init__(parent)
        self._rotulo_todos = rotulo_todos
        self.setPopupMode(QToolButton.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)

        self._menu = QMenu(self)
        self._checkboxes = []  # lista de (valor, QCheckBox)

        for valor, texto in opcoes:
            checkbox = QCheckBox(texto)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._ao_mudar)
            acao = QWidgetAction(self._menu)
            acao.setDefaultWidget(checkbox)
            self._menu.addAction(acao)
            self._checkboxes.append((valor, checkbox))

        self.setMenu(self._menu)
        self._atualizar_texto()

    def _ao_mudar(self):
        self._atualizar_texto()
        self.alteracao.emit()

    def _atualizar_texto(self):
        selecionados = self.valores_selecionados()
        total = len(self._checkboxes)
        if len(selecionados) == total or len(selecionados) == 0:
            self.setText(f"{self._rotulo_todos} ▾")
        elif len(selecionados) == 1:
            texto = next(t for v, cb in self._checkboxes if cb.isChecked() for t in [cb.text()])
            self.setText(f"{texto} ▾")
        else:
            self.setText(f"{len(selecionados)} selecionados ▾")

    def valores_selecionados(self):
        """Lista dos valores cujas checkboxes estão marcadas."""
        return [valor for valor, cb in self._checkboxes if cb.isChecked()]

    def filtro_ativo(self):
        """True se nem todos (nem nenhum) estão selecionados, ou seja, se filtra mesmo algo."""
        n = len(self.valores_selecionados())
        return 0 < n < len(self._checkboxes)

    def selecionar_todos(self):
        for _, cb in self._checkboxes:
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self._atualizar_texto()
