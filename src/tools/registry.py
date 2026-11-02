"""Catálogo das ferramentas para o LLM: schemas (formato OpenAI/Groq) + execução por nome.

Liga as funções puras de src/tools aos schemas Pydantic. Não conhece nenhum framework.
"""
from typing import Any

from src.tools.orders import ConsultaPedidoInput, consultar_pedido
from src.tools.policies import BuscaPoliticaInput, PolicyRetriever, buscar_politica
from src.tools.products import (BuscaProdutoInput, DisponibilidadeInput,
                                buscar_produto, consultar_disponibilidade)


def _simplificar(no: Any) -> Any:
    """Deixa o JSON Schema do Pydantic no formato simples que os provedores esperam.

    Optional[X] vira X (some o anyOf com null), e saem `title` e `default: null`.
    """
    if isinstance(no, list):
        return [_simplificar(i) for i in no]
    if not isinstance(no, dict):
        return no
    if "anyOf" in no:
        opcoes = [o for o in no["anyOf"] if o.get("type") != "null"]
        if len(opcoes) == 1:
            resto = {k: v for k, v in no.items() if k != "anyOf"}
            return _simplificar({**opcoes[0], **resto})
    return {k: _simplificar(v) for k, v in no.items()
            if not (k == "title" and isinstance(v, str)) and not (k == "default" and v is None)}


class Ferramentas:
    """`specs` vai para o LLM; `executar` roda a chamada pedida e devolve o JSON do resultado."""

    def __init__(self, repos, retriever: PolicyRetriever):
        # nome -> (schema de entrada, função, descrição para o LLM)
        self._catalogo = {
            "buscar_produto": (
                BuscaProdutoInput, lambda e: buscar_produto(repos, e),
                "Busca produtos no catálogo por nome, categoria e/ou faixa de preço. Use SEMPRE antes de falar "
                "de preço, estoque ou disponibilidade. Devolve preço original, desconto, preço final e uma "
                "frase pronta (preco_texto)."),
            "consultar_disponibilidade": (
                DisponibilidadeInput, lambda e: consultar_disponibilidade(repos, e),
                "Detalhes de um produto (estoque, especificações, situação) pelo product_id obtido em "
                "buscar_produto. Se estiver indisponível, devolve alternativas."),
            "consultar_pedido": (
                ConsultaPedidoInput, lambda e: consultar_pedido(repos, e),
                "Status, itens, rastreio e previsão de um pedido. Exige número do pedido E e-mail da compra "
                "(verificação). Não chame sem os dois: peça ao cliente."),
            "buscar_politica": (
                BuscaPoliticaInput, lambda e: buscar_politica(retriever, e),
                "Busca no manual de políticas da loja: trocas, devoluções, arrependimento, garantia, pagamento, "
                "parcelamento, frete, entrega, promoções, horários, endereço e contato. Devolve trechos com a fonte."),
        }
        self.specs: list[dict[str, Any]] = [
            {"type": "function",
             "function": {"name": nome, "description": descricao,
                          "parameters": _simplificar(schema.model_json_schema())}}
            for nome, (schema, _, descricao) in self._catalogo.items()
        ]

    def executar(self, nome: str, args: dict[str, Any]) -> str:
        """Valida os argumentos no schema da tool e devolve o resultado como JSON."""
        schema, funcao, _ = self._catalogo[nome]
        return funcao(schema.model_validate(args)).model_dump_json()