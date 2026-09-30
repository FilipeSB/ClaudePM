"""Formatação partilhada entre vistas."""


def fmt_pct(valor) -> str:
    """Percentagem com uma casa decimal (ex: 70 -> '70.0%')."""
    try:
        return f"{float(valor or 0):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"
