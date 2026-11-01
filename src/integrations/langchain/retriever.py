"""Recuperação dos trechos relevantes do manual, sempre com a fonte (página e seção).

Quem usa o retriever (tools, agente) só vê `PolicyRetriever.search()` e `PolicyChunk`,
tipos do projeto: nada de LangChain vaza para fora de `src/integrations/`.

Para inspecionar a recuperação ANTES de conectar o LLM:

    python -m src.integrations.langchain.retriever "posso devolver minha compra?"
    python -m src.integrations.langchain.retriever          # roda perguntas de exemplo
"""

import sys

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from src.integrations.langchain.embeddings import get_embeddings
from src.integrations.langchain.pdf_loader import load_pdf_pages
from src.integrations.langchain.vector_store import build_vector_store
from src.rag.chunking import chunk_pages
from src.rag.document_loader import DEFAULT_PDF
from src.rag.models import PolicyChunk

DEFAULT_K = 4


class PolicyRetriever:
    """Busca semântica nas políticas da loja."""

    def __init__(self, store: Chroma, k: int = DEFAULT_K):
        self._store = store
        self._k = k

    def search(self, query: str, k: int | None = None) -> list[PolicyChunk]:
        """Os k trechos mais parecidos com a pergunta, do mais ao menos relevante."""
        results = self._store.similarity_search_with_score(query, k=k or self._k)
        return [
            PolicyChunk(
                text=doc.page_content,
                page=doc.metadata["page"],
                section=doc.metadata["section"],
                section_id=doc.metadata["section_id"],
                score=round(1 - distance, 4),  # no Chroma com cosseno: distância = 1 - similaridade
            )
            for doc, distance in results
        ]


def build_policy_retriever(
    pdf_path=DEFAULT_PDF, embeddings: Embeddings | None = None, k: int = DEFAULT_K
) -> PolicyRetriever:
    """PDF -> páginas -> chunks -> embeddings -> Chroma -> retriever."""
    chunks = chunk_pages(load_pdf_pages(pdf_path))
    store = build_vector_store(chunks, embeddings or get_embeddings())
    return PolicyRetriever(store, k)


SAMPLE_QUESTIONS = [
    "Qual o horário de funcionamento aos sábados?",
    "Me arrependi da compra, posso devolver?",
    "Posso parcelar em 10x? Qual a parcela mínima?",
    "Comprei com defeito, posso trocar?",
]

if __name__ == "__main__":
    retriever = build_policy_retriever()
    for question in sys.argv[1:] or SAMPLE_QUESTIONS:
        print(f"\n>> {question}")
        for chunk in retriever.search(question):
            first_line = chunk.text.split("\n")[1] if "\n" in chunk.text else ""
            print(f"  [{chunk.score:.3f}] p.{chunk.page} | {chunk.section}\n          {first_line[:90]}")