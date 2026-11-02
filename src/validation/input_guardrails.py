"""Guardrails de entrada: checagens determinísticas, antes de qualquer chamada ao LLM.

Cobre mensagem vazia/longa, prompt injection óbvio e pedidos de dados de terceiros.
O escopo semântico (assunto sem relação com a loja) NÃO é decidido aqui: palavras-chave
errariam em "vocês vendem cabos?", que é pergunta da loja (Manual §7.1). Isso fica com o
classificador do grafo (rota `fora_do_escopo`).
"""
import re
from typing import Literal

from pydantic import BaseModel

from src.tools.common import normalizar

MAX_CHARS = 1000


class Bloqueio(BaseModel):
    motivo: Literal["vazia", "longa", "injecao", "terceiros"]
    resposta: str  # pronta para o cliente, no tom da loja


_RESPOSTAS = {
    "vazia": "Opa, não recebi nenhuma mensagem. Como posso te ajudar? 🎸",
    "longa": f"Sua mensagem ficou bem longa (o limite é {MAX_CHARS} caracteres). Pode resumir o que você precisa?",
    "injecao": ("Não consigo mudar a forma como funciono, mas posso te ajudar com instrumentos, "
                "pedidos e políticas da Empório da Música. O que você procura?"),
    "terceiros": ("Por privacidade, só consulto um pedido quando você me passa o número dele e o e-mail usado "
                  "na compra, e não listo nem compartilho dados de outros clientes. "
                  "Se tiver esses dados do seu pedido, me manda aqui!"),
}

# Padrões sobre o texto normalizado (minúsculas, sem acento). Propositalmente estreitos:
# "ignore o violão vermelho" ou "quais as regras de troca?" não podem ser bloqueados.
_INJECAO = [re.compile(p) for p in (
    r"\b(ignore|ignorar|esqueca|esquecer|desconsidere|desobedeca)\b.{0,40}\b(instrucoes|prompt|orientacoes|comandos|regras (anteriores|acima|internas|do sistema))",
    r"ignore (all|previous|the above)|disregard .{0,30}(instructions|rules)|forget .{0,30}instructions",
    r"\b(revele|mostre|exiba|repita|imprima|me passe|me mostre|me diga)\b.{0,30}\b(seu prompt|suas instrucoes|suas regras internas|suas orientacoes)",
    r"system prompt|prompt do sistema|prompt inicial",
    r"\bvoce (agora )?(e|sera|vai ser|passa a ser)\b.{0,30}\b(sem (restricoes|regras|filtros)|outro (assistente|bot|robo|ia)|hacker|administrador|desenvolvedor)",
    r"\b(finja|faca de conta|aja como|atue como)\b.{0,30}\b(sem (regras|restricoes|filtros)|desenvolvedor|administrador|hacker)",
    r"jailbreak|modo (dan|desenvolvedor|dev|deus|admin\w*)",
)]

# Enumeração ou busca de dados de outros clientes. Quem tem pedido + e-mail passa pela tool.
# "Todas as compras acima de R$ 500 têm frete grátis?" é pergunta legítima: só pegamos listagens explícitas.
_TERCEIROS = [re.compile(p) for p in (
    r"\b(lista|listagem|relatorio)\b.{0,20}\b(pedidos|clientes|compras)\b",
    r"\btodos (os )?(pedidos|clientes)\b.{0,15}\b(de hoje|da loja|do sistema|cadastrados)\b",
    r"\btodos (os )?clientes\b",
    r"\b(pedidos?|compras?|dados|cadastro|telefone|e-?mail|cpf|endereco)\b.{0,25}\b(outr[oa]s? clientes?|de terceiros|dos clientes|do cliente|da cliente)\b",
    r"\bquem (comprou|e o cliente|foi o cliente)\b",
)]


def _bloqueio(motivo: str) -> Bloqueio:
    return Bloqueio(motivo=motivo, resposta=_RESPOSTAS[motivo])


def verificar_entrada(texto: str) -> Bloqueio | None:
    """Devolve um Bloqueio (com a resposta pronta) ou None se a mensagem pode seguir."""
    texto = texto.strip()
    if not texto:
        return _bloqueio("vazia")
    if len(texto) > MAX_CHARS:
        return _bloqueio("longa")
    limpo = normalizar(texto)
    if any(p.search(limpo) for p in _INJECAO):
        return _bloqueio("injecao")
    if any(p.search(limpo) for p in _TERCEIROS):
        return _bloqueio("terceiros")
    return None