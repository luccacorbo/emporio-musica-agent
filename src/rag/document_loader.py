"""Parte do carregamento do PDF que não depende de framework.

A extração em si (PyPDFLoader) fica em `src/integrations/langchain/pdf_loader.py`.
"""

from pathlib import Path

from src.rag.models import Page

DEFAULT_PDF = Path(__file__).resolve().parents[2] / "data" / "raw" / "politicas_da_loja.pdf"

# Cabeçalho + rodapé sozinhos já somam ~65 caracteres; uma página "real" tem bem mais.
MIN_CHARS_PER_PAGE = 100

# Num texto normal a linha mediana tem várias palavras; com 1 palavra por linha, a extração falhou.
MIN_MEDIAN_WORDS_PER_LINE = 2


class DocumentError(Exception):
    """PDF ausente ou com páginas sem texto extraído."""


def check_pages_have_text(pages: list[Page], min_chars: int = MIN_CHARS_PER_PAGE) -> None:
    """Levanta DocumentError se não houver páginas ou se alguma estiver (quase) vazia.

    Página sem texto costuma ser PDF digitalizado (imagem): seria preciso OCR.
    Melhor falhar aqui do que indexar um manual incompleto e responder errado depois.
    """
    if not pages:
        raise DocumentError("Nenhuma página encontrada no PDF.")
    empty = [p.number for p in pages if len(p.text.strip()) < min_chars]
    if empty:
        raise DocumentError(
            f"Páginas sem texto extraído (menos de {min_chars} caracteres): {empty}. "
            "O PDF pode ser digitalizado; seria necessário OCR."
        )


def check_lines_are_readable(pages: list[Page], min_median_words: int = MIN_MEDIAN_WORDS_PER_LINE) -> None:
    """Levanta DocumentError se o texto veio "uma palavra por linha".

    Alguns PDFs guardam cada palavra como um objeto separado; o modo de extração padrão
    então perde as quebras de linha reais, e os títulos de seção deixam de ser reconhecíveis.
    Sem essa checagem o erro seria silencioso: todos os chunks cairiam na mesma seção.
    """
    word_counts = sorted(len(line.split()) for page in pages for line in page.text.split("\n") if line.strip())
    median = word_counts[len(word_counts) // 2] if word_counts else 0
    if median < min_median_words:
        raise DocumentError(
            f"Texto extraído com {median} palavra(s) por linha (mediana): as quebras de linha foram perdidas. "
            "Use extraction_mode='layout' no PyPDFLoader."
        )