import sys
from PySide6.QtWidgets import QApplication

from database.db import init_db
from ui.janela_principal import JanelaPrincipal


def main():
    init_db()
    app = QApplication(sys.argv)
    janela = JanelaPrincipal()
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
