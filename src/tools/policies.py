"""Tool de políticas: buscar_politica (RAG sobre o manual)."""
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.rag.models import PolicyChunk


class PolicyRetriever(Protocol):
    """Contrato mínimo do retriever (a implementação fica em integrations/)."""
    def search(self, question: str) -> list[PolicyChunk]: ...


class BuscaPoliticaInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    pergunta: str = Field(
        min_length=3, max_length=500,
        description="Dúvida do cliente sobre regras da loja (trocas, devoluções, pagamento, frete, garantia, horários).",
    )


class TrechoPolitica(BaseModel):
    texto: str
    fonte: str  # ex.: "Manual de Políticas, p. 4, seção 4.1 ..."


class ResultadoPolitica(BaseModel):
    trechos: list[TrechoPolitica]
    mensagem: str | None = None


def buscar_politica(retriever: PolicyRetriever, entrada: BuscaPoliticaInput) -> ResultadoPolitica:
    chunks = retriever.search(entrada.pergunta)
    if not chunks:
        return ResultadoPolitica(
            trechos=[],
            mensagem="Nenhum trecho do manual encontrado. Não invente a regra; encaminhe para a equipe.",
        )
    return ResultadoPolitica(trechos=[TrechoPolitica(texto=c.text, fonte=c.source) for c in chunks])