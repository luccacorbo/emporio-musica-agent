"""Nós do grafo. Cada nó recebe o estado e devolve só o que muda.

As dependências (LLM, ferramentas, relógio) entram por `criar_nos`. O LLM é o `LLMClient`
do projeto (src/agent/llm.py), não um modelo de framework.
"""
import logging
from collections.abc import Callable
from datetime import datetime

from src.agent.llm import LLMClient, LLMError, Message
from src.agent.prompts import FATOS_DO_PROMPT, PROMPT_CLASSIFICADOR, prompt_agente, prompt_conversa
from src.agent.rotas import ROTA_PADRAO, interpretar_rota
from src.integrations.langgraph.state import EstadoAgente
from src.tools.registry import Ferramentas
from src.validation.output_validation import Evidencia, validar_resposta
from src.validation.tool_validation import validar_chamada

log = logging.getLogger(__name__)
log_reclamacoes = logging.getLogger("emporio.reclamacoes")

HISTORICO_CLASSIFICADOR = 6  # últimas falas consideradas para classificar ("e o preço?" depende do contexto)
MAX_CORRECOES = 1            # quantas vezes o agente pode tentar de novo após uma resposta rejeitada
PREFIXO_ERRO = "ERRO: "      # marca resultados de ferramenta que falharam (não valem como evidência)
MSG_RESPOSTA_INSEGURA = ("Não consegui confirmar essa informação com segurança, e prefiro não te passar "
                         "nada errado 🙏 Pode reformular a pergunta?")


def conversa_simples(mensagens: list[Message]) -> list[Message]:
    """Só falas do cliente e respostas finais. Sem chamadas e resultados de ferramentas.

    Os nós sem ferramentas não podem receber tool calls no histórico (o provedor recusa).
    """
    return [m for m in mensagens
            if m.role == "user"
            or (m.role == "assistant" and not m.tool_calls and (m.content or "").strip())]


def _falas_do_cliente(mensagens: list[Message]) -> list[str]:
    return [m.content or "" for m in mensagens if m.role == "user"]


def _evidencias(mensagens: list[Message]) -> list[Evidencia]:
    """Resultados das tools (sem os que deram erro) + fatos fixos do prompt.

    A mensagem de resultado não guarda o nome da tool: ele vem da chamada com o mesmo id.
    """
    nomes = {c.id: c.name for m in mensagens for c in m.tool_calls}
    tools = [Evidencia(nomes.get(m.tool_call_id or "", ""), m.content or "")
             for m in mensagens
             if m.role == "tool" and not (m.content or "").startswith(PREFIXO_ERRO)]
    return [*tools, Evidencia("prompt", FATOS_DO_PROMPT)]


def criar_nos(llm: LLMClient, ferramentas: Ferramentas, agora: Callable[[], datetime]) -> dict[str, Callable]:

    def classificar(estado: EstadoAgente) -> dict:
        historico = conversa_simples(estado["messages"])[-HISTORICO_CLASSIFICADOR:]
        try:
            resposta = llm.complete([Message(role="system", content=PROMPT_CLASSIFICADOR), *historico])
            rota = interpretar_rota(resposta.content)
        except LLMError:  # classificador falhou: o agente também recusa o que é de fora (regra 8)
            log.warning("Falha ao classificar; usando '%s'.", ROTA_PADRAO, exc_info=True)
            rota = ROTA_PADRAO
        return {"rota": rota}

    def agente(estado: EstadoAgente) -> dict:
        sistema = prompt_agente(agora())
        if estado.get("problemas"):  # retry: a correção vai no system prompt, não no histórico
            sistema += ("\n\nCORREÇÃO: sua resposta anterior foi rejeitada na verificação: "
                        + " ".join(estado["problemas"])
                        + " Consulte as ferramentas se precisar e responda de novo usando só dados consultados, "
                          "citando a fonte (página e seção) das regras do manual. Não mencione esta correção ao cliente.")
        resposta = llm.complete([Message(role="system", content=sistema), *estado["messages"]],
                                ferramentas.specs)
        if resposta.tool_calls:  # vai executar ferramentas: a chamada entra no histórico
            return {"messages": [resposta.to_message()]}
        return {"rascunho": resposta.content}  # resposta final: só entra no histórico depois de validada

    def executar_ferramentas(estado: EstadoAgente) -> dict:
        """Executa as tool calls do LLM, recusando as inválidas (argumentos ou origem dos dados)."""
        falas = _falas_do_cliente(estado["messages"])
        resultados = []
        for chamada in estado["messages"][-1].tool_calls:
            # Modelos Llama costumam mandar null em parâmetros opcionais: tratamos como "não informado".
            args = {k: v for k, v in chamada.arguments.items() if v is not None}
            erro = validar_chamada(chamada.name, args, falas)
            saida = None
            if erro is None:
                try:
                    saida = ferramentas.executar(chamada.name, args)
                except Exception:  # falha inesperada da tool: o LLM recebe um erro, o grafo segue
                    log.exception("Falha ao executar %s", chamada.name)
                    erro = "Erro ao executar a ferramenta. Tente de novo ou encaminhe para a equipe."
            resultados.append(Message(role="tool", tool_call_id=chamada.id,
                                      content=f"{PREFIXO_ERRO}{erro}" if erro else saida))
        return {"messages": resultados}

    def responder_direto(estado: EstadoAgente) -> dict:
        """Saudação, escopo e reclamação: resposta sem ferramentas."""
        conversa = conversa_simples(estado["messages"])
        if estado["rota"] == "reclamacao":
            # Stub (Manual §7.3): só registra em log. Em produção iria para um sistema de tickets.
            log_reclamacoes.warning("Reclamação registrada: %s", conversa[-1].content)
        resposta = llm.complete(
            [Message(role="system", content=prompt_conversa(agora(), estado["rota"])), *conversa])
        return {"rascunho": resposta.content}

    def validar_saida(estado: EstadoAgente) -> dict:
        """Confere o rascunho contra as consultas. Aprovado entra no histórico; rejeitado vai a retry/fallback."""
        mensagens = estado["messages"]
        rascunho = estado["rascunho"]
        problemas = validar_resposta(rascunho, _evidencias(mensagens), _falas_do_cliente(mensagens))
        if not problemas:
            return {"messages": [Message(role="assistant", content=rascunho)], "problemas": []}

        log.warning("Resposta rejeitada: %s", problemas)
        tentativas = estado.get("tentativas", 0)
        if estado["rota"] == "da_loja" and tentativas < MAX_CORRECOES:
            return {"problemas": problemas, "tentativas": tentativas + 1}
        return {"messages": [Message(role="assistant", content=MSG_RESPOSTA_INSEGURA)], "problemas": []}

    return {"classificar": classificar, "agente": agente, "ferramentas": executar_ferramentas,
            "responder_direto": responder_direto, "validar_saida": validar_saida}