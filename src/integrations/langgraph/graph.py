"""Monta o grafo e expõe `Agente.responder(texto, conversa_id)`, o ponto de entrada do CLI."""
import logging
from collections.abc import Callable
from datetime import datetime

from langgraph.graph import END, START, StateGraph

from src.agent.llm import LLMClient, LLMError, Message
from src.agent.prompts import MENSAGEM_ERRO, agora_em_campo_grande
from src.integrations.langgraph.edges import (depois_de_classificar, depois_de_validar_saida,
                                              depois_do_agente)
from src.integrations.langgraph.nodes import criar_nos
from src.integrations.langgraph.state import EstadoAgente
from src.tools.registry import Ferramentas
from src.validation.input_guardrails import verificar_entrada

log = logging.getLogger(__name__)

LIMITE_PASSOS = 20  # classificar + 2 rodadas de ferramentas + 1 correção cabem folgados


class Agente:
    """Guarda o histórico de cada conversa em memória (some ao encerrar o processo).

    O histórico só é atualizado quando o turno termina bem: uma falha no meio nunca deixa
    chamada de ferramenta sem resposta nem mensagem rejeitada para trás.
    """

    def __init__(self, grafo):
        self.grafo = grafo
        self._historico: dict[str, list[Message]] = {}

    def historico(self, conversa_id: str = "default") -> list[Message]:
        return list(self._historico.get(conversa_id, []))

    def responder(self, mensagem: str, conversa_id: str = "default") -> str:
        """Uma volta de conversa."""
        # Guardrail de entrada fora do grafo: mensagem bloqueada não custa LLM nem entra no histórico.
        bloqueio = verificar_entrada(mensagem)
        if bloqueio:
            log.info("Entrada bloqueada (%s)", bloqueio.motivo)
            return bloqueio.resposta

        entrada = {
            "messages": [*self.historico(conversa_id), Message(role="user", content=mensagem.strip())],
            "tentativas": 0,
            "problemas": [],
        }
        try:
            estado = self.grafo.invoke(entrada, {"recursion_limit": LIMITE_PASSOS})
        except Exception as erro:
            if not isinstance(erro, LLMError) and type(erro).__name__ != "GraphRecursionError":
                raise
            log.exception("Turno abortado")
            return MENSAGEM_ERRO

        self._historico[conversa_id] = estado["messages"]
        return estado["messages"][-1].content or ""

    def mermaid(self) -> str:
        """Diagrama do grafo (para o README)."""
        return self.grafo.get_graph().draw_mermaid()


def criar_agente(llm: LLMClient, ferramentas: Ferramentas,
                 agora: Callable[[], datetime] = agora_em_campo_grande) -> Agente:
    nos = criar_nos(llm, ferramentas, agora)

    g = StateGraph(EstadoAgente)
    for nome, no in nos.items():
        g.add_node(nome, no)

    g.add_edge(START, "classificar")
    g.add_conditional_edges("classificar", depois_de_classificar, ["agente", "responder_direto"])
    g.add_conditional_edges("agente", depois_do_agente, ["ferramentas", "validar_saida"])
    g.add_edge("ferramentas", "agente")
    g.add_edge("responder_direto", "validar_saida")
    g.add_conditional_edges("validar_saida", depois_de_validar_saida, ["agente", END])

    return Agente(g.compile())