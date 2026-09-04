"""
Utilitários de exportação de tabelas para Excel (.xlsx) e PDF.
"""
from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm


def exportar_excel(caminho: str, titulo: str, colunas: list, linhas: list):
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31] if titulo else "Dados"

    ws.append(colunas)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for linha in linhas:
        ws.append(linha)

    for col_cells in ws.columns:
        largura = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells) + 2
        ws.column_dimensions[col_cells[0].column_letter].width = min(largura, 50)

    wb.save(caminho)


def exportar_pdf(caminho: str, titulo: str, colunas: list, linhas: list):
    doc = SimpleDocTemplate(caminho, pagesize=landscape(A4),
                             leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                             topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    estilos = getSampleStyleSheet()
    elementos = [Paragraph(titulo, estilos["Title"]), Spacer(1, 12)]

    dados_tabela = [colunas] + linhas
    tabela = Table(dados_tabela, repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F5496")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elementos.append(tabela)
    doc.build(elementos)
