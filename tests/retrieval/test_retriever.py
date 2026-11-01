"""Testes da integração LangChain/Chroma: leitura do PDF, índice e retriever.

Três grupos:
  1. PDF real (rápido): extração e cobertura de páginas.
  2. Plumbing: Chroma + retriever com embeddings falsos e determinísticos.
  3. Recuperação real (marcados `embeddings`): modelo multilíngue de verdade.
Os grupos 1 e 3 rodam só se data/raw/politicas_da_loja.pdf existir.
"""

import math
import re
import zlib

import pytest
from langchain_core.embeddings import Embeddings

from src.integrations.langchain.pdf_loader import load_pdf_pages
from src.integrations.langchain.retriever import PolicyRetriever, build_policy_retriever
from src.integrations.langchain.vector_store import build_vector_store
from src.rag.chunking import MAX_CHARS, chunk_pages
from src.rag.document_loader import DEFAULT_PDF, DocumentError
from src.rag.models import Page, PolicyChunk

needs_pdf = pytest.mark.skipif(not DEFAULT_PDF.exists(), reason="data/raw/politicas_da_loja.pdf não encontrado")


# --------------------------------------------------------------------------- #
# 1. PDF real
# --------------------------------------------------------------------------- #
def test_missing_pdf_raises(tmp_path):
    with pytest.raises(DocumentError, match="não encontrado"):
        load_pdf_pages(tmp_path / "nao_existe.pdf")


@needs_pdf
def test_real_pdf_all_pages_have_text_and_are_chunked():
    pages = load_pdf_pages()
    chunks = chunk_pages(pages)

    assert [p.number for p in pages] == list(range(1, 9))
    assert {c.page for c in chunks} == set(range(1, 9))  # nenhuma página ficou de fora
    assert all(len(c.text) <= MAX_CHARS + 120 for c in chunks)
    expected = {"2", "3", "3.1", "4.1", "4.2", "4.3", "4.4", "5.1", "5.2", "6.2", "7.1", "7.3", "8.1"}
    assert expected <= {c.section_id for c in chunks}


# --------------------------------------------------------------------------- #
# 2. Plumbing: Chroma + retriever com embeddings falsos
# --------------------------------------------------------------------------- #
class BagOfWordsEmbeddings(Embeddings):
    """Embedding determinístico por contagem de palavras (hash). Só para testar a infraestrutura."""

    DIM = 512

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.DIM
        for word in re.findall(r"\w+", text.lower()):
            vec[zlib.crc32(word.encode()) % self.DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts):
        return [self._embed(t) for t in texts]

    def embed_query(self, text):
        return self._embed(text)


SAMPLE_PAGES = [
    Page(number=1, text="EMPÓRIO DA MÚSICA\nRua 14 de Maio, 3200 — Centro\nCampo Grande – MS\n(67) 3341-4444"),
    Page(number=4, text="""4. Política de Trocas e Devoluções
4.1 Direito de Arrependimento (Compras Online)
• O cliente pode solicitar a devolução em até 7 (sete) dias corridos após o recebimento.
• O reembolso será realizado em até 10 dias úteis.
4.2 Trocas por Defeito
• Produtos com defeito de fabricação podem ser trocados em até 30 (trinta) dias."""),
    Page(number=5, text="""2. Horário de Funcionamento
Segunda a Sexta-feira 09:00 às 18:00
Sábado 09:00 às 13:00
Domingo e Feriados Fechado"""),
]


@pytest.fixture
def fake_retriever():
    chunks = chunk_pages(SAMPLE_PAGES)
    return PolicyRetriever(build_vector_store(chunks, BagOfWordsEmbeddings()), k=3), chunks


def test_retriever_returns_project_types_with_source(fake_retriever):
    retriever, _ = fake_retriever
    best = retriever.search("devolução em até 7 dias após o recebimento")[0]

    assert isinstance(best, PolicyChunk)
    assert best.section_id == "4.1"
    assert best.page == 4
    assert "p. 4" in best.source and "4.1" in best.source


def test_retriever_respects_k_and_orders_by_score(fake_retriever):
    retriever, _ = fake_retriever
    results = retriever.search("dias úteis")

    assert len(results) == 3
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)
    assert all(0 <= r.score <= 1 for r in results)
    assert len(retriever.search("dias úteis", k=1)) == 1


def test_score_is_cosine_similarity(fake_retriever):
    retriever, _ = fake_retriever
    emb = BagOfWordsEmbeddings()
    query = "devolução 7 dias recebimento"
    best = retriever.search(query)[0]
    manual = sum(a * b for a, b in zip(emb.embed_query(query), emb.embed_query(best.text)))

    assert best.score == pytest.approx(manual, abs=1e-3)


def test_rebuilding_index_does_not_duplicate_chunks():
    chunks = chunk_pages(SAMPLE_PAGES)
    build_vector_store(chunks, BagOfWordsEmbeddings())
    store = build_vector_store(chunks, BagOfWordsEmbeddings())

    assert len(PolicyRetriever(store).search("qualquer coisa", k=100)) == len(chunks)


# --------------------------------------------------------------------------- #
# 3. Recuperação real (PDF + modelo de embeddings multilíngue)
# --------------------------------------------------------------------------- #
# (pergunta, seções aceitas entre os k resultados, trecho que deve aparecer no texto recuperado)
RETRIEVAL_CASES = [
    # horários
    ("Qual o horário de funcionamento aos sábados?", {"2"}, "09:00 às 13:00"),
    ("A loja abre no domingo?", {"2"}, "Domingo e Feriados"),
    # devoluções
    ("Me arrependi da compra, posso devolver?", {"4.1"}, "7 (sete) dias"),
    ("Em quanto tempo recebo o reembolso?", {"4.1"}, "10 dias úteis"),
    # trocas
    ("Comprei com defeito, posso trocar?", {"4.2"}, "30 (trinta) dias"),
    ("Quero trocar a cor do produto que comprei", {"4.3"}, "preferência"),
    ("Quais itens não podem ser trocados?", {"4.4"}, "Boquilhas"),
    # pagamentos
    ("Vocês aceitam PIX? Tem desconto?", {"3"}, "5% de desconto"),
    ("Posso parcelar em 10x? Qual a parcela mínima?", {"3.1"}, "R$ 100,00"),
    # entrega e escopo
    ("O frete é grátis?", {"5.1"}, "R$ 500,00"),
    ("Quanto tempo demora o SEDEX para outra cidade?", {"5.2"}, "SEDEX"),
    ("Vocês vendem cordas e palhetas?", {"1", "7.1"}, "acessórios"),
]


@pytest.fixture(scope="module")
def real_retriever():
    return build_policy_retriever(k=4)  # baixa o modelo de embeddings na 1ª execução


@needs_pdf
@pytest.mark.embeddings
@pytest.mark.parametrize(("question", "expected_sections", "expected_text"), RETRIEVAL_CASES)
def test_real_retrieval_finds_the_right_policy(real_retriever, question, expected_sections, expected_text):
    results = real_retriever.search(question)
    ranking = [(r.section_id, r.score) for r in results]

    hits = [r for r in results if r.section_id in expected_sections]
    assert hits, f"'{question}': esperado {expected_sections}, recuperado {ranking}"
    assert any(expected_text in r.text for r in hits), f"'{question}': trecho '{expected_text}' ausente"