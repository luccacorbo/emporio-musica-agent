"""Tool de pedidos: consultar_pedido (número + e-mail verificados juntos)."""
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.tools.common import brl

NAO_ENCONTRADO = (
    "Não encontrei um pedido com esse número e e-mail. "
    "Confira os dados e tente novamente."
)  # mesma mensagem para pedido inexistente e e-mail errado (não revela quais pedidos existem)

_SITUACAO = {
    "pending": "Aguardando confirmação do pagamento.",
    "confirmed": "Pedido confirmado; ainda não foi despachado.",
    "shipped": "Pedido despachado e a caminho.",
    "delivered": "Pedido entregue.",
    "cancelled": "Pedido cancelado.",
}


class ConsultaPedidoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    numero_pedido: str = Field(
        min_length=1, max_length=30,
        description="Número do pedido informado pelo cliente (pode vir com '#').",
    )
    email: EmailStr = Field(description="E-mail cadastrado na compra; obrigatório para a verificação.")


class ItemPedido(BaseModel):
    produto: str
    quantidade: int


class PedidoInfo(BaseModel):
    numero_pedido: str
    data: str
    status: str
    situacao: str
    itens: list[ItemPedido]
    total: float
    total_texto: str
    forma_pagamento: str
    codigo_rastreio: str | None
    aviso_rastreio: str | None
    previsao_entrega: str | None
    observacoes: str | None


class ResultadoPedido(BaseModel):
    encontrado: bool
    mensagem: str | None = None
    pedido: PedidoInfo | None = None


def _forma_pagamento(codigo: str) -> str:
    if codigo.startswith("credit_"):
        return f"Cartão de crédito em {codigo.split('_', 1)[1]}"
    return {"pix": "PIX", "boleto": "Boleto", "debit": "Cartão de débito"}.get(codigo, codigo)


def _aviso_rastreio(status: str, codigo: str | None) -> str | None:
    if codigo:
        return None
    if status in ("pending", "confirmed"):
        return ("Ainda sem código de rastreio: ele é enviado por e-mail e WhatsApp "
                "assim que o pedido é despachado (Manual §5.3).")
    if status in ("shipped", "delivered"):
        return "O código de rastreio não consta no sistema; encaminhe para a equipe."
    return None


def _item(repos, item) -> ItemPedido:
    """Único ponto que conhece os campos de OrderItem."""
    produto = repos.products.get(item.product_id)
    return ItemPedido(produto=produto.name if produto else str(item.product_id),
                      quantidade=item.quantity)


def consultar_pedido(repos, entrada: ConsultaPedidoInput) -> ResultadoPedido:
    numero = entrada.numero_pedido.lstrip("#").strip()
    pedido = repos.orders.get(numero) or repos.orders.get(numero.upper())
    cliente = repos.customers.get(pedido.customer_id) if pedido else None

    email_ok = bool(cliente) and cliente.email.strip().casefold() == entrada.email.strip().casefold()
    if not email_ok:
        return ResultadoPedido(encontrado=False, mensagem=NAO_ENCONTRADO)

    codigo = pedido.tracking_code or None
    info = PedidoInfo(
        numero_pedido=str(pedido.order_id),
        data=str(pedido.order_date),
        status=pedido.status,
        situacao=_SITUACAO.get(pedido.status, pedido.status),
        itens=[_item(repos, i) for i in repos.orders.get_items(pedido.order_id)],
        total=pedido.total_brl,
        total_texto=brl(pedido.total_brl),
        forma_pagamento=_forma_pagamento(pedido.payment_method),
        codigo_rastreio=codigo,
        aviso_rastreio=_aviso_rastreio(pedido.status, codigo),
        previsao_entrega=str(pedido.estimated_delivery) if pedido.estimated_delivery else None,
        observacoes=pedido.notes or None,
    )
    return ResultadoPedido(encontrado=True, pedido=info)