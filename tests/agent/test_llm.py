import json
from types import SimpleNamespace

import groq
import httpx
import pytest

from src.agent.llm import GroqLLMClient, LLMError, Message, ToolCall

REQ = httpx.Request("POST", "https://api.groq.com")


def _raw(content=None, tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _tool_call(name="search_products", arguments='{"query": "violão"}', id="call_1"):
    return SimpleNamespace(id=id, function=SimpleNamespace(name=name, arguments=arguments))


class FakeGroq:
    """Imita client.chat.completions.create: devolve (ou levanta) os itens da fila, em ordem."""

    def __init__(self, *items):
        self.queue = list(items)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _llm(*items):
    fake = FakeGroq(*items)
    return GroqLLMClient(client=fake, model="modelo-teste"), fake


USER = [Message(role="user", content="oi")]


def test_resposta_normal():
    llm, fake = _llm(_raw("  Fala, músico!  "))
    resp = llm.complete(USER)
    assert resp.content == "Fala, músico!"
    assert fake.calls[0]["model"] == "modelo-teste"
    assert "tools" not in fake.calls[0]


def test_resposta_vazia_tenta_de_novo():
    llm, fake = _llm(_raw("   "), _raw("Agora foi"))
    assert llm.complete(USER).content == "Agora foi"
    assert len(fake.calls) == 2


def test_resposta_vazia_duas_vezes_levanta_erro():
    llm, _ = _llm(_raw(None), _raw(""))
    with pytest.raises(LLMError, match="vazia"):
        llm.complete(USER)


def test_sem_choices_conta_como_vazia():
    llm, _ = _llm(SimpleNamespace(choices=[]), SimpleNamespace(choices=[]))
    with pytest.raises(LLMError):
        llm.complete(USER)


def test_tool_call_e_interpretada():
    llm, fake = _llm(_raw(None, [_tool_call()]))
    tools = [{"type": "function", "function": {"name": "search_products"}}]
    resp = llm.complete(USER, tools=tools)
    assert resp.tool_calls == [ToolCall(id="call_1", name="search_products",
                                        arguments={"query": "violão"})]
    assert fake.calls[0]["tools"] == tools
    assert fake.calls[0]["tool_choice"] == "auto"


def test_argumentos_de_tool_nao_json():
    llm, _ = _llm(_raw(None, [_tool_call(arguments="{quebrado")]))
    with pytest.raises(LLMError, match="inválidos"):
        llm.complete(USER)


def test_argumentos_de_tool_nao_objeto():
    llm, _ = _llm(_raw(None, [_tool_call(arguments="[1, 2]")]))
    with pytest.raises(LLMError, match="objeto"):
        llm.complete(USER)


def test_erro_de_conexao_vira_llmerror():
    llm, _ = _llm(groq.APIConnectionError(request=REQ))
    with pytest.raises(LLMError, match="conectar"):
        llm.complete(USER)


def test_erro_http_vira_llmerror_com_status():
    erro = groq.RateLimitError("limite", response=httpx.Response(429, request=REQ), body=None)
    llm, _ = _llm(erro)
    with pytest.raises(LLMError, match="429"):
        llm.complete(USER)


def test_sem_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqLLMClient()


def test_historico_com_tool_e_serializado_no_formato_da_api():
    llm, fake = _llm(_raw("ok"))
    messages = [
        Message(role="system", content="sys"),
        Message(role="user", content="preço do violão?"),
        Message(role="assistant", tool_calls=[ToolCall(id="c1", name="x", arguments={"q": "violão"})]),
        Message(role="tool", content='{"preco": 1}', tool_call_id="c1"),
    ]
    llm.complete(messages)
    sent = fake.calls[0]["messages"]
    assert sent[2]["tool_calls"][0]["function"]["name"] == "x"
    assert json.loads(sent[2]["tool_calls"][0]["function"]["arguments"]) == {"q": "violão"}
    assert sent[3]["tool_call_id"] == "c1"