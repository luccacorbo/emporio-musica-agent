"""Utilitários compartilhados pelas tools (sem framework)."""
import unicodedata


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento, para comparar textos digitados pelo cliente."""
    decomposto = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
    return sem_acento.casefold().strip()


def brl(valor: float) -> str:
    """1234.5 -> 'R$ 1.234,50'."""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"