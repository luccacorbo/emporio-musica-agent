"""Embeddings multilíngues locais (sem API key)."""

import os

from langchain_core.embeddings import Embeddings

# ~470 MB, 100+ idiomas (inclui português), contexto de 512 tokens. Baixado na 1ª execução.
DEFAULT_MODEL = "intfloat/multilingual-e5-small"


class PrefixedEmbeddings(Embeddings):
    """HuggingFaceEmbeddings com prefixo opcional em consultas e documentos.

    Os modelos E5 foram treinados com "query: " e "passage: " na frente do texto;
    sem os prefixos a qualidade da busca cai.
    """

    def __init__(self, model_name: str, query_prefix: str = "", document_prefix: str = ""):
        # Import tardio: só carrega torch/sentence-transformers quando o modelo é de fato usado.
        from langchain_huggingface import HuggingFaceEmbeddings

        self._model = HuggingFaceEmbeddings(model_name=model_name, encode_kwargs={"normalize_embeddings": True})
        self._query_prefix = query_prefix
        self._document_prefix = document_prefix

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.embed_documents([self._document_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._model.embed_query(self._query_prefix + text)


def get_embeddings(model_name: str | None = None) -> Embeddings:
    """Modelo padrão (E5 small); troque com o argumento ou a variável EMBEDDING_MODEL."""
    model_name = model_name or os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)
    is_e5 = "e5" in model_name.lower()
    return PrefixedEmbeddings(model_name, "query: " if is_e5 else "", "passage: " if is_e5 else "")
