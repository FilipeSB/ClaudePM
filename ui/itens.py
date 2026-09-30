"""Item de tabela com ordenação inteligente (partilhado por todas as vistas)."""
import re
from PySide6.QtWidgets import QTableWidgetItem

_REGEX_NUMERO = re.compile(r"-?\d+(?:\.\d+)?")


def _tentar_converter_numero(texto):
    """Interpreta '70.0%', '2,520.00' ou '12' como número; None se não for número."""
    t = (texto or "").strip()
    if not t:
        return None
    limpo = t.rstrip("%").replace(",", "").strip()
    if _REGEX_NUMERO.fullmatch(limpo):
        return float(limpo)
    return None


def _chave_ordenacao(texto):
    """
    Ordem total e consistente: vazios < números (por valor) < texto (sem
    distinguir maiúsculas). Uma ordem total evita comparações contraditórias
    que podem causar comportamento indefinido no algoritmo de ordenação do Qt.
    """
    if texto is None or texto.strip() == "":
        return (0, 0.0, "")
    n = _tentar_converter_numero(texto)
    if n is not None:
        return (1, n, "")
    return (2, 0.0, texto.casefold())


class ItemOrdenavel(QTableWidgetItem):
    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            return _chave_ordenacao(self.text()) < _chave_ordenacao(other.text())
        return super().__lt__(other)
