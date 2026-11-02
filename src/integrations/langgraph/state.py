"""Estado do grafo, com as mensagens do próprio projeto (src.agent.llm.Message)."""
from operator import add
from typing import Annotated, TypedDict

from src.agent.llm import Message
from src.agent.rotas import Rota


class EstadoAgente(TypedDict):
    messages: Annotated[list[Message], add]  # histórico; cada nó devolve só o que acrescenta
    rota: Rota
    rascunho: str          # resposta candidata, ainda não validada (só vira mensagem se aprovada)
    tentativas: int        # correções já pedidas neste turno
    problemas: list[str]   # motivos da última rejeição; vazio = nada a corrigir