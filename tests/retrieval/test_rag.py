"""Testes da parte do RAG que não depende de framework: verificação de páginas e chunking."""

import re

import pytest

from src.rag.chunking import MAX_CHARS, chunk_pages, clean_text, split_long_text
from src.rag.document_loader import DocumentError, check_pages_have_text, check_lines_are_readable
from src.rag.models import Page

HEADER = "Empório da Música Manual de Políticas e Procedimentos"

# Duas páginas em memória que reproduzem a estrutura do manual.
PAGE_4 = Page(number=4, text=f"""{HEADER}
4. Política de Trocas e Devoluções
A Empório segue o Código de Defesa do Consumidor.
4.1 Direito de Arrependimento (Compras Online)
• O cliente pode solicitar a devolução em até 7 (sete) dias corridos após o recebimento.
• O reembolso será realizado em até 10 dias úteis.
5. Política de Frete e Entregas
5.2 Entregas para Outras Cidades
Página 4""")

PAGE_5 = Page(number=5, text=f"""{HEADER}
Utilizamos os Correios (PAC e SEDEX) e a Jadlog. PAC leva de 5 a 12 dias úteis.
7.2 Fluxo de Atendimento Padrão
1. Saudação: cumprimentar o cliente pelo nome.
2. Entendimento: identificar a necessidade do cliente.
Página 5""")

COVER = Page(number=1, text="EMPÓRIO DA MÚSICA\nRua 14 de Maio, 3200 — Centro\nCampo Grande – MS\n(67) 3341-4444")


# --------------------------------------------------------------------------- #
# Verificação de páginas
# --------------------------------------------------------------------------- #
def test_pages_with_text_pass():
    check_pages_have_text([PAGE_4, PAGE_5])


def test_empty_page_is_reported_by_number():
    with pytest.raises(DocumentError, match=r"\[2\]"):
        check_pages_have_text([PAGE_4, Page(number=2, text="")])


def test_page_with_only_header_and_footer_is_reported():
    with pytest.raises(DocumentError, match=r"\[3\]"):
        check_pages_have_text([PAGE_4, PAGE_5, Page(number=3, text=f"{HEADER}\nPágina 3")])


def test_no_pages_raises():
    with pytest.raises(DocumentError):
        check_pages_have_text([])


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #
def test_clean_text_drops_noise_and_blank_lines():
    assert clean_text(f"{HEADER}\r\n\r\nTexto útil\r\nPágina 7") == ["Texto útil"]


def test_header_and_footer_are_removed():
    for chunk in chunk_pages([PAGE_4, PAGE_5]):
        assert "Manual de Políticas e Procedimentos" not in chunk.text
        assert not re.search(r"Página \d", chunk.text)


def test_chunk_has_section_path_page_and_ids():
    chunk = next(c for c in chunk_pages([PAGE_4, PAGE_5]) if c.section_id == "4.1")

    assert chunk.text.startswith("4. Política de Trocas e Devoluções > 4.1 Direito de Arrependimento")
    assert "7 (sete) dias" in chunk.text
    assert chunk.page == 4
    assert chunk.section == "4.1 Direito de Arrependimento (Compras Online)"


def test_section_continues_on_next_page_and_empty_body_is_dropped():
    chunks = chunk_pages([PAGE_4, PAGE_5])
    sec_52 = [c for c in chunks if c.section_id == "5.2"]

    # O título 5.2 está no fim da página 4 (sem texto); o conteúdo está na página 5.
    assert [c.page for c in sec_52] == [5]
    assert "PAC leva de 5 a 12 dias" in sec_52[0].text
    assert all(c.text.split("\n", 1)[1].strip() for c in chunks)  # nenhum chunk vazio


def test_numbered_list_items_are_not_headings():
    chunks = chunk_pages([PAGE_4, PAGE_5])
    fluxo = [c for c in chunks if c.section_id == "7.2"]

    assert len(fluxo) == 1 and "1. Saudação: cumprimentar" in fluxo[0].text
    assert not any(c.section_id == "1" for c in chunks)


def test_text_before_first_heading_is_cover():
    chunks = chunk_pages([COVER, PAGE_4])

    assert chunks[0].section == "Capa" and chunks[0].page == 1
    assert "Rua 14 de Maio, 3200" in chunks[0].text


# --------------------------------------------------------------------------- #
# Divisão de seções longas
# --------------------------------------------------------------------------- #
LONG_BODY = "\n".join(f"• Regra número {i} da garantia com texto suficiente para ocupar espaço." for i in range(40))


def test_short_text_is_not_split():
    assert split_long_text("linha 1\nlinha 2") == ["linha 1\nlinha 2"]


def test_long_text_is_split_respecting_limit_and_keeping_whole_lines():
    parts = split_long_text(LONG_BODY, max_chars=300, overlap=100)

    assert len(parts) > 1
    assert all(len(p) <= 300 for p in parts)
    assert set(LONG_BODY.split("\n")) == {line for p in parts for line in p.split("\n")}  # nada se perde


def test_consecutive_parts_overlap():
    parts = split_long_text(LONG_BODY, max_chars=300, overlap=100)

    for before, after in zip(parts, parts[1:]):
        assert before.split("\n")[-1] == after.split("\n")[0]  # a última linha se repete na parte seguinte


def test_every_part_of_a_long_section_keeps_title_and_page():
    chunks = chunk_pages([Page(number=7, text=f"8. Garantia\n{LONG_BODY}")])

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.text.startswith("8. Garantia\n")
        assert len(chunk.text) <= MAX_CHARS + len("8. Garantia\n")
        assert chunk.page == 7 and chunk.section_id == "8"

# --------------------------------------------------------------------------- #
# Texto no formato que o PyPDFLoader devolve para PDFs com uma palavra por objeto
# --------------------------------------------------------------------------- #
WORD_PER_LINE = Page(number=2, text="Empório\n \nda\n \nMúsica\n \nManual\n \nde\n \nPolíticas\n \n1.\n \nSobre\n \na\n \nEmpório")


def test_word_per_line_text_is_rejected():
    with pytest.raises(DocumentError, match="palavra"):
        check_lines_are_readable([WORD_PER_LINE])


def test_normal_text_is_accepted_as_readable():
    check_lines_are_readable([PAGE_4, PAGE_5, COVER])


def test_clean_text_collapses_layout_mode_spacing():
    raw = f"{HEADER}\n1. Sobre    a Empório     da  Música\nPIX      Pagamento\xa0à vista     5% de desconto\nPágina 2"

    assert clean_text(raw) == ["1. Sobre a Empório da Música", "PIX Pagamento à vista 5% de desconto"]


def test_headings_are_found_in_layout_mode_text_with_extra_spaces():
    page = Page(number=4, text="4.1    Direito  de   Arrependimento (Compras Online)\n•  O cliente pode devolver em até 7 (sete) dias.")
    chunk = chunk_pages([page])[0]

    assert chunk.section_id == "4.1" and chunk.section == "4.1 Direito de Arrependimento (Compras Online)"