"""Desenho partilhado das barras de percentagem (Calendário e Alocação)."""
from PySide6.QtGui import QColor, QPainter
from PySide6.QtCore import Qt, QRect, QRectF
from utils.formatacao import fmt_pct
from utils.cores import cor_texto_para


def desenhar_barra(painter: QPainter, rect: QRect, pct: float, cor_hex: str):
    """
    Barra cujo comprimento é proporcional à percentagem (100% = largura toda),
    na cor indicada. Acima de 100% fica cheia, com contorno vermelho.
    O texto muda de cor consoante está sobre a parte preenchida ou sobre o
    fundo, para se ler sempre bem.
    """
    pct = float(pct or 0)
    cor = QColor(cor_hex)
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)

    painter.setPen(QColor("#D32F2F") if pct > 100 else QColor("#bbbbbb"))
    painter.setBrush(QColor("#EDEDED"))
    painter.drawRoundedRect(rect, 3, 3)

    largura = int(rect.width() * min(pct, 100.0) / 100.0)
    area_cheia = QRect(rect.x(), rect.y(), largura, rect.height())
    if largura > 0:
        painter.setPen(Qt.NoPen)
        painter.setBrush(cor)
        painter.drawRoundedRect(area_cheia, 3, 3)

    texto = fmt_pct(pct)
    cor_sobre_cheio = QColor(cor_texto_para(cor_hex))

    # parte do texto que cai sobre a barra preenchida
    painter.setClipRect(area_cheia)
    painter.setPen(cor_sobre_cheio)
    painter.drawText(rect, Qt.AlignCenter, texto)
    # parte do texto que cai sobre o fundo claro
    painter.setClipRect(QRect(rect.x() + largura, rect.y(), rect.width() - largura, rect.height()))
    painter.setPen(QColor("#111111"))
    painter.drawText(rect, Qt.AlignCenter, texto)
    painter.restore()
