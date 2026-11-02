"""Decisões de caminho do grafo. Funções puras do estado, sem LLM."""
from langgraph.graph import END

from src.integrations.langgraph.state import EstadoAgente


def depois_de_classificar(estado: EstadoAgente) -> str:
    """Só assuntos da loja chegam às ferramentas; o resto responde direto."""
    return "agente" if estado["rota"] == "da_loja" else "responder_direto"


def depois_do_agente(estado: EstadoAgente) -> str:
    """Pediu ferramentas (a chamada é a última mensagem): executa. Senão, o rascunho vai para a validação."""
    return "ferramentas" if estado["messages"][-1].tool_calls else "validar_saida"


def depois_de_validar_saida(estado: EstadoAgente) -> str:
    """Há problemas e ainda cabe correção: volta ao agente. Senão, termina."""
    return "agente" if estado.get("problemas") else END