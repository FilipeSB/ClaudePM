"""Cores das pessoas (usadas no Calendário e na Alocação)."""

# Paleta de cores distintas: usada como cor por defeito de cada pessoa nova
# e como alternativa para pessoas sem cor escolhida.
PALETA_PESSOAS = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC949", "#AF7AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
]


def cor_valida(texto) -> bool:
    return (
        isinstance(texto, str) and len(texto) == 7 and texto.startswith("#")
        and all(c in "0123456789abcdefABCDEF" for c in texto[1:])
    )


def cor_da_pessoa(cor_guardada, pessoa_id=0) -> str:
    """A cor escolhida para a pessoa; se não tiver (ou for inválida), uma cor da paleta (estável por id)."""
    if cor_valida(cor_guardada):
        return cor_guardada
    return PALETA_PESSOAS[int(pessoa_id or 0) % len(PALETA_PESSOAS)]


def cor_sugerida_para_nova_pessoa(n_pessoas_existentes: int) -> str:
    return PALETA_PESSOAS[n_pessoas_existentes % len(PALETA_PESSOAS)]


def cor_texto_para(fundo_hex: str) -> str:
    """Preto ou branco, consoante o que se lê melhor sobre a cor de fundo (luminância percebida)."""
    if not cor_valida(fundo_hex):
        return "#000000"
    r, g, b = (int(fundo_hex[i:i + 2], 16) for i in (1, 3, 5))
    luminancia = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luminancia > 150 else "#FFFFFF"
