import sys
import os
import traceback
import logging
from datetime import datetime

from PySide6.QtWidgets import QApplication, QMessageBox

from database.db import init_db, PASTA_DADOS
from ui.janela_principal import JanelaPrincipal


def _configurar_logging():
    """
    Guarda um ficheiro de log de erros em %APPDATA%\\GestaoProjetos\\erros.log
    (ou ~/.gestaoprojetos/erros.log fora do Windows). Isto é essencial porque
    a app corre em modo --windowed (sem consola), pelo que qualquer erro que
    antes seria invisível (e podia parecer um "fecho inesperado" sem
    explicação) passa a ficar registado aqui para diagnóstico.
    """
    caminho_log = os.path.join(PASTA_DADOS, "erros.log")
    logging.basicConfig(
        filename=caminho_log,
        level=logging.ERROR,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    return caminho_log


def _instalar_captura_global_de_erros(caminho_log):
    """
    Por defeito, uma excepção Python não tratada que ocorra dentro de um
    "slot" do Qt (ex: ao clicar num botão) pode fazer a aplicação terminar
    de forma abrupta e sem qualquer aviso -- especialmente numa app gerada
    com PyInstaller em modo --windowed, onde não há consola nenhuma a
    mostrar o erro. Isto substitui o comportamento por defeito: qualquer
    erro não tratado passa a ser registado no ficheiro de log e mostrado
    num aviso ao utilizador, em vez de fazer a app desaparecer sem
    explicação.
    """
    def gerir_excecao(tipo, valor, tb):
        mensagem_completa = "".join(traceback.format_exception(tipo, valor, tb))
        logging.error(mensagem_completa)
        try:
            QMessageBox.critical(
                None, "Ocorreu um erro inesperado",
                "A aplicação encontrou um erro inesperado, mas foi possível continuar.\n\n"
                f"Detalhe: {valor}\n\n"
                f"Os detalhes completos foram guardados em:\n{caminho_log}\n\n"
                "Se isto continuar a acontecer, envia este ficheiro para diagnóstico."
            )
        except Exception:
            # Se nem sequer for possível mostrar a mensagem (ex: erro muito
            # cedo no arranque, antes de haver QApplication), pelo menos o
            # log já foi escrito acima.
            pass

    sys.excepthook = gerir_excecao


def main():
    caminho_log = _configurar_logging()
    _instalar_captura_global_de_erros(caminho_log)

    try:
        init_db()
    except Exception:
        logging.error("Falha ao inicializar a base de dados:\n" + traceback.format_exc())
        raise

    app = QApplication(sys.argv)
    janela = JanelaPrincipal()
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
