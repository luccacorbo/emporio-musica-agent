"""Divide o manual em chunks por seção, preservando título e número da página.
Cada chunk começa com o caminho da seção ("4. Trocas > 4.1 Arrependimento"), que dá
contexto ao embedding e ao LLM. Chunks nunca atravessam páginas, então o número da
página é sempre exato.
"""

import re
import unicodedata

from src.rag.models import Chunk, Page

MAX_CHARS = 900
OVERLAP = 100

# Cabeçalho e rodapé repetidos em toda página: ruído para a busca.
_NOISE = re.compile(r"^(Empório da Música\s+Manual de Políticas e Procedimentos|Página\s+\d+)$")

# "4. Título" (seção) ou "4.1 Título" (subseção). Título sem ":" e sem ponto final,
# o que evita confundir com itens de lista como "1. Saudação: cumprimentar ...".
_HEADING = re.compile(
    r"^(?:(?P<sub>\d{1,2}\.\d{1,2})|(?P<top>\d{1,2})\.)\s+(?P<title>[A-ZÀ-Ý][^:]{2,80})(?<![.,;])$"
)

COVER = "Capa"


def clean_text(text: str) -> list[str]:
    """Normaliza o texto e devolve as linhas úteis (sem cabeçalho, rodapé e linhas vazias)."""
    text = unicodedata.normalize("NFC", text).replace("\r", "").replace("\xa0", " ")
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n"))  # o modo layout deixa espaços extras
    return [line for line in lines if line and not _NOISE.match(line)]


def split_long_text(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[str]:
    """Quebra um texto grande em partes de até `max_chars`, sempre em fim de linha.

    Cada parte repete no início as últimas linhas da anterior (até `overlap`
    caracteres), para que uma regra no limite entre duas partes não se perca.
    Linhas maiores que `max_chars` não são cortadas (no manual, nenhuma é).
    """
    parts: list[str] = []
    current: list[str] = []
    for line in text.split("\n"):
        if current and len("\n".join([*current, line])) > max_chars:
            parts.append("\n".join(current))
            tail: list[str] = []
            for previous in reversed(current):
                if sum(len(t) + 1 for t in tail) + len(previous) > overlap:
                    break
                tail.insert(0, previous)
            current = tail if len("\n".join([*tail, line])) <= max_chars else []
        current.append(line)
    if current:
        parts.append("\n".join(current))
    return parts


def chunk_pages(pages: list[Page], max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[Chunk]:
    """Transforma páginas em chunks com página, seção e id da seção."""
    chunks: list[Chunk] = []

    # A seção corrente continua valendo na página seguinte (ex.: 5.2 começa numa página
    # e a tabela aparece na próxima), por isso o estado vive fora do loop de páginas.
    top, sub, section_id = COVER, None, "capa"

    for page in pages:
        body_lines: list[str] = []

        def emit() -> None:
            body = "\n".join(body_lines).strip()
            body_lines.clear()
            if not body:  # título no fim da página, sem texto: nada a indexar
                return
            path = top if sub is None else f"{top} > {sub}"
            for part in split_long_text(body, max_chars, overlap):
                chunks.append(Chunk(text=f"{path}\n{part}", page=page.number, section=sub or top, section_id=section_id))

        for line in clean_text(page.text):
            heading = _HEADING.match(line)
            if heading is None:
                body_lines.append(line)
                continue
            emit()  # fecha o bloco anterior (ainda com o título anterior)
            if heading["top"]:
                top, sub, section_id = f"{heading['top']}. {heading['title']}", None, heading["top"]
            else:
                sub, section_id = f"{heading['sub']} {heading['title']}", heading["sub"]
        emit()

    return chunks