"""Índice vetorial das políticas no Chroma."""

import os

# Evita a tentativa de enviar telemetria do Chroma (gera erros/ruído em alguns ambientes).
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from langchain_chroma import Chroma  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402

from src.rag.models import Chunk  # noqa: E402

COLLECTION_NAME = "politicas_loja"


def build_vector_store(chunks: list[Chunk], embeddings: Embeddings) -> Chroma:
    """Indexa os chunks em uma coleção Chroma (em memória) com distância de cosseno."""
    store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        collection_metadata={"hnsw:space": "cosine"},
    )
    store.reset_collection()  # o Chroma em memória é compartilhado no processo: evita duplicar chunks
    store.add_documents(
        [
            Document(
                page_content=c.text,
                metadata={"page": c.page, "section": c.section, "section_id": c.section_id},
            )
            for c in chunks
        ]
    )
    return store