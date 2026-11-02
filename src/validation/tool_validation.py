"""Valida a chamada de ferramenta pedida pelo LLM antes de executá-la. Sem framework.

1. Argumentos: reaproveita os schemas Pydantic das próprias tools (tipos, faixas, obrigatórios).
2. Privacidade (LGPD): número do pedido e e-mail precisam ter sido ditos pelo CLIENTE nesta
   conversa. Assim o LLM não consegue chutar um e-mail nem reaproveitar um dado de outra origem.
"""
import re

from pydantic import ValidationError

from src.tools.common import normalizar
from src.tools.orders import ConsultaPedidoInput
from src.tools.policies import BuscaPoliticaInput
from src.tools.products import BuscaProdutoInput, DisponibilidadeInput

_SCHEMAS = {
    "buscar_produto": BuscaProdutoInput,
    "consultar_disponibilidade": DisponibilidadeInput,
    "consultar_pedido": ConsultaPedidoInput,
    "buscar_politica": BuscaPoliticaInput,
}

ERRO_ORIGEM_PEDIDO = (
    "O número do pedido e o e-mail precisam ter sido informados pelo cliente nesta conversa. "
    "Peça ao cliente o que faltar; não use dados de outra origem."
)


def _formatar(erro: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc'])) or 'entrada'}: {e['msg']}" for e in erro.errors())


def _origem_do_pedido(entrada: ConsultaPedidoInput, falas_cliente: list[str]) -> str | None:
    texto = normalizar(" ".join(falas_cliente))
    numero = normalizar(entrada.numero_pedido.lstrip("#"))
    # fronteira de palavra: o pedido "1234" não pode ser aceito só porque o cliente disse "12345"
    numero_ok = re.search(rf"(?<!\w){re.escape(numero)}(?!\w)", texto) is not None
    email_ok = normalizar(entrada.email) in texto
    return None if numero_ok and email_ok else ERRO_ORIGEM_PEDIDO


def validar_chamada(nome: str, args: dict, falas_cliente: list[str]) -> str | None:
    """Devolve a mensagem de erro (para o LLM corrigir) ou None se a chamada pode executar."""
    schema = _SCHEMAS.get(nome)
    if schema is None:
        return f"Ferramenta desconhecida: {nome}."
    try:
        entrada = schema.model_validate(args)
    except ValidationError as erro:
        return f"Argumentos inválidos: {_formatar(erro)}. Se faltar informação do cliente, peça a ele."
    if nome == "consultar_pedido":
        return _origem_do_pedido(entrada, falas_cliente)
    return None