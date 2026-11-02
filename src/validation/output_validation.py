"""Valida a resposta final contra o que as ferramentas devolveram (a "evidência").

A evidência são os resultados das tools, que o cliente nunca vê. A resposta só pode afirmar
valores, prazos, status, rastreio, estoque e regras da loja que existam ali (ou que o próprio
cliente disse). A resposta também não pode expor instruções internas nem citar o manual.
Verificação determinística (regex), não um segundo LLM: grátis, previsível e testável.
Devolve a lista de problemas; vazia = resposta liberada.
"""
import json
import math
import re
from typing import NamedTuple

from src.tools.common import brl


class Evidencia(NamedTuple):
    ferramenta: str  # nome da tool (ou "prompt" para fatos fixos das instruções)
    conteudo: str    # JSON devolvido pela tool


# ---------- Extração de "fatos" numéricos ----------

_BRL = re.compile(r"R\$\s*(\d+(?:\.\d{3})*)(?:,(\d{1,2}))?")
_PRAZO = re.compile(r"(\d+(?:,\d+)?)\s*(dias?|horas?|meses|anos?|x\b|%)", re.I)
_PAREN = re.compile(r"(\d+)\s*\([^)\d]*\)")  # "7 (sete) dias" -> "7 dias" (como o manual escreve)
_UNIDADE = {"dia": "dias", "hora": "horas", "ano": "anos"}


def _fatos(texto: str) -> set[tuple[str, float]]:
    """Valores em reais e prazos/percentuais/parcelas: {("R$", 1200.0), ("dias", 7.0), ("x", 12.0)}."""
    texto = _PAREN.sub(r"\1", texto)
    fatos = {("R$", round(float(f"{m[1].replace('.', '')}.{(m[2] or '0').ljust(2, '0')}"), 2))
             for m in _BRL.finditer(texto)}
    for m in _PRAZO.finditer(texto):
        unidade = m[2].lower()
        fatos.add((_UNIDADE.get(unidade, unidade), float(m[1].replace(",", "."))))
    return fatos


def _com_parcelas(fatos: set[tuple[str, float]]) -> set[tuple[str, float]]:
    """Aceita valor ÷ 2..12 (parcelas calculadas a partir de um preço consultado)."""
    derivados = set()
    for unidade, valor in fatos:
        if unidade == "R$":
            for n in range(2, 13):
                derivados |= {("R$", round(valor / n, 2)), ("R$", math.floor(valor / n * 100) / 100)}
    return fatos | derivados


def _json(texto: str) -> dict:
    try:
        dado = json.loads(texto)
    except ValueError:
        return {}
    return dado if isinstance(dado, dict) else {}


# ---------- Verificações ----------

def _fatos_sem_evidencia(resposta, evidencias, falas) -> list[str]:
    """Todo número da resposta precisa existir nas consultas (inclui os trechos do manual)."""
    aceitos = _com_parcelas(_fatos(" ".join([e.conteudo for e in evidencias] + falas)))
    problemas = []
    for unidade, valor in sorted(_fatos(resposta) - aceitos):
        if unidade == "R$":
            problemas.append(f"O valor {brl(valor)} não consta nas consultas.")
        else:
            problemas.append(f"'{valor:g} {unidade}' não consta nas consultas nem no manual.")
    return problemas


_STATUS = {"entregue": "delivered", "despachad": "shipped", "enviad": "shipped", "a caminho": "shipped",
           "cancelad": "cancelled", "confirmad": "confirmed", "aguardando": "pending"}
_AFIRMA_STATUS = re.compile(
    r"\bpedido\b[^.!?\n]{0,30}?\b(?:foi|est[aá]|ficou|segue)\s+(?:j[aá]\s+)?"
    r"(entregue|despachad|enviad|a caminho|cancelad|confirmad|aguardando)", re.I)


def _status_de_pedido(resposta, evidencias) -> list[str]:
    reais = {(_json(e.conteudo).get("pedido") or {}).get("status")
             for e in evidencias if e.ferramenta == "consultar_pedido"} - {None}
    return [f"Status de pedido afirmado ('{m[1]}') não confere com a consulta (status real: {sorted(reais) or 'nenhuma consulta'})."
            for m in _AFIRMA_STATUS.finditer(resposta) if _STATUS[m[1].lower()] not in reais]


_CODIGO = re.compile(r"\bBR[A-Z0-9]{9}BR\b", re.I)


def _rastreio(resposta, evidencias, falas) -> list[str]:
    conhecido = " ".join([e.conteudo for e in evidencias] + falas).upper()
    return [f"O código de rastreio {c} não consta nas consultas."
            for c in sorted({m.upper() for m in _CODIGO.findall(resposta)}) if c not in conhecido]


_ESTOQUE = re.compile(r"\bem estoque\b|\b(?:est[aá]|est[aã]o|temos|tem)\s+dispon[ií]ve", re.I)
_NEGACAO = re.compile(r"\b(n[ãa]o|sem|nem)\b", re.I)


def _estoque(resposta, evidencias) -> list[str]:
    afirma = any(not _NEGACAO.search(resposta[max(0, m.start() - 30):m.start()])
                 for m in _ESTOQUE.finditer(resposta))
    consultado = any('"situacao":"disponivel"' in e.conteudo for e in evidencias
                     if e.ferramenta in ("buscar_produto", "consultar_disponibilidade"))
    return ["Disponibilidade afirmada sem nenhum produto disponível nas consultas."] if afirma and not consultado else []


# Termos que só aparecem quando a resposta AFIRMA uma regra da loja. Estreito de propósito:
# "devolução" ou "frete" sozinhos também aparecem em perguntas ("qual a data de recebimento?").
_REGRA_DA_LOJA = re.compile(
    r"reembols|sem juros|frete gr[aá]tis|arrependimento|garantia (?:legal|do fabricante)", re.I)


def _regra_sem_consulta(resposta, evidencias) -> list[str]:
    """Regra da loja afirmada sem nenhum trecho do manual consultado (alucinação sem número)."""
    if not _REGRA_DA_LOJA.search(resposta):
        return []
    consultou = any(e.ferramenta == "buscar_politica" and _json(e.conteudo).get("trechos")
                    for e in evidencias)
    return [] if consultou else ["Regra da loja afirmada sem consulta ao manual (use buscar_politica)."]


_VAZAMENTO = ("regras de atendimento", "preco_texto", "buscar_produto", "consultar_disponibilidade",
              "consultar_pedido", "buscar_politica", "system prompt")

# Citação do manual interno ("Manual de Políticas, p. 4, seção 4.1"). Estreito de propósito:
# "manual" sozinho apareceria em "com todos os acessórios e manuais".
_CITACAO_MANUAL = re.compile(r"manual de pol[ií]ticas|manual interno|\bp\.\s*\d|se[çc][ãa]o\s+\d", re.I)


def _vazamento(resposta) -> list[str]:
    texto = resposta.casefold()
    problemas = []
    if any(t in texto for t in _VAZAMENTO):
        problemas.append("A resposta expõe instruções ou nomes internos.")
    if _CITACAO_MANUAL.search(resposta):
        problemas.append("A resposta cita página, seção ou nome do manual interno; reescreva sem citar a fonte.")
    return problemas


def validar_resposta(resposta: str, evidencias: list[Evidencia], falas_cliente: list[str]) -> list[str]:
    """Problemas encontrados na resposta; lista vazia = pode entregar ao cliente."""
    return [
        *_fatos_sem_evidencia(resposta, evidencias, falas_cliente),
        *_status_de_pedido(resposta, evidencias),
        *_rastreio(resposta, evidencias, falas_cliente),
        *_estoque(resposta, evidencias),
        *_regra_sem_consulta(resposta, evidencias),
        *_vazamento(resposta),
    ]