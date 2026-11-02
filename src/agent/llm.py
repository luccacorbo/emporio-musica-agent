"""Contrato genérico com o LLM + implementação para o Groq (API compatível com OpenAI)."""
import json
import os
from typing import Any, Literal, Protocol

import groq
from groq import Groq
from pydantic import BaseModel, Field

from src.agent.prompts import MENSAGEM_ERRO, build_system_prompt

DEFAULT_MODEL = "openai/gpt-oss-20b"


class LLMError(Exception):
    """Qualquer falha na comunicação com o modelo (rede, HTTP, resposta vazia/inválida)."""


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)  # só em role="assistant"
    tool_call_id: str | None = None  # só em role="tool"


class LLMResponse(BaseModel):
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)

    def to_message(self) -> Message:
        """Forma de guardar a resposta no histórico."""
        return Message(role="assistant", content=self.content or None, tool_calls=self.tool_calls)


class LLMClient(Protocol):
    """Contrato que o orquestrador usa. Outro provedor = outra classe com este método."""

    def complete(self, messages: list[Message],
                 tools: list[dict[str, Any]] | None = None) -> LLMResponse: ...


def _to_api(m: Message) -> dict[str, Any]:
    data: dict[str, Any] = {"role": m.role, "content": m.content or ""}
    if m.tool_calls:
        data["tool_calls"] = [
            {"id": c.id, "type": "function",
             "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)}}
            for c in m.tool_calls
        ]
    if m.tool_call_id:
        data["tool_call_id"] = m.tool_call_id
    return data


def _parse(raw: Any) -> LLMResponse:
    if not raw.choices:
        return LLMResponse()
    msg = raw.choices[0].message
    calls = []
    for c in msg.tool_calls or []:
        try:
            args = json.loads(c.function.arguments or "{}")
        except json.JSONDecodeError as e:
            raise LLMError(f"Argumentos inválidos na chamada da ferramenta '{c.function.name}'.") from e
        if not isinstance(args, dict):
            raise LLMError(f"Argumentos da ferramenta '{c.function.name}' não são um objeto.")
        calls.append(ToolCall(id=c.id, name=c.function.name, arguments=args))
    return LLMResponse(content=(msg.content or "").strip(), tool_calls=calls)


class GroqLLMClient:
    def __init__(self, api_key: str | None = None, model: str | None = None,
                 temperature: float = 0.3, max_tokens: int = 800, client: Any = None):
        """`client` permite injetar um Groq falso nos testes."""
        api_key = api_key or os.getenv("GROQ_API_KEY")
        if client is None and not api_key:
            raise LLMError("GROQ_API_KEY não definida (veja .env.example).")
        self.model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)
        self.temperature = temperature
        self.max_tokens = max_tokens
        # O SDK já faz 2 retries para erros de rede/429/5xx.
        self._client = client or Groq(api_key=api_key, timeout=30.0, max_retries=2)

    def complete(self, messages: list[Message],
                 tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        for _ in range(2):  # 1 nova tentativa se a resposta vier vazia
            response = self._call(messages, tools)
            if response.content or response.tool_calls:
                return response
        raise LLMError("O modelo devolveu uma resposta vazia.")

    def _call(self, messages: list[Message], tools: list[dict[str, Any]] | None) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [_to_api(m) for m in messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        try:
            raw = self._client.chat.completions.create(**kwargs)
        except groq.APIConnectionError as e:  # inclui timeout
            raise LLMError("Não consegui conectar à API do Groq.") from e
        except groq.APIStatusError as e:
            raise LLMError(f"Erro da API do Groq (HTTP {e.status_code}).") from e
        return _parse(raw)


def main() -> None:
    """Conversa de terminal com o modelo (sem ferramentas): `python -m src.agent.llm`."""
    from dotenv import load_dotenv

    load_dotenv()
    llm = GroqLLMClient()
    history: list[Message] = []
    print(f"Modelo: {llm.model}. Digite 'sair' para encerrar.\n")
    while True:
        texto = input("Você: ").strip()
        if texto.lower() in {"sair", "exit", "quit"}:
            break
        if not texto:
            continue
        history.append(Message(role="user", content=texto))
        # O prompt é remontado a cada turno para a data/hora e o status da loja ficarem atuais.
        messages = [Message(role="system", content=build_system_prompt())] + history
        try:
            resposta = llm.complete(messages)
        except LLMError as e:
            history.pop()
            print(f"[erro] {e}\nAgente: {MENSAGEM_ERRO}\n")
            continue
        history.append(resposta.to_message())
        print(f"Agente: {resposta.content}\n")


if __name__ == "__main__":
    main()