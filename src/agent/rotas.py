"""Rotas do roteador e leitura da resposta do classificador. Sem framework."""
from typing import Literal, get_args

from src.tools.common import normalizar

Rota = Literal["da_loja", "reclamacao", "social", "fora_do_escopo"]
ROTAS: tuple[str, ...] = get_args(Rota)
ROTA_PADRAO: Rota = "da_loja"  # na dúvida, o agente decide (e ele também recusa o que é de fora)


def interpretar_rota(texto: str) -> Rota:
    """Extrai a rota da resposta do LLM, tolerando maiúsculas, acento e frases ao redor.

    Se aparecer mais de uma, vale a primeira. Se nenhuma, `da_loja`.
    """
    limpo = normalizar(texto).replace(" ", "_")
    achadas = [(limpo.find(rota), rota) for rota in ROTAS if rota in limpo]
    return min(achadas)[1] if achadas else ROTA_PADRAO