"""Tipos do RAG, independentes de qualquer framework (LangChain, Chroma, etc.)."""

from pydantic import BaseModel


class Page(BaseModel):
    """Texto extraído de uma página do PDF."""

    number: int  # começa em 1
    text: str


class Chunk(BaseModel):
    """Trecho do manual pronto para indexar."""

    text: str  # primeira linha = caminho da seção; depois o conteúdo
    page: int  # página do PDF (começa em 1)
    section: str  # ex.: "4.1 Direito de Arrependimento (Compras Online)"
    section_id: str  # ex.: "4.1"


class PolicyChunk(Chunk):
    """Trecho devolvido pela busca, com a similaridade em relação à pergunta."""

    score: float  # similaridade de cosseno, de 0 a 1 (maior = mais parecido)

    @property
    def source(self) -> str:
        return f"Manual de Políticas, p. {self.page}, seção {self.section}"