"""A composição aceita dependências injetadas e o CLI conversa até 'sair'."""
from pathlib import Path

from src.agent.llm import LLMResponse
from src.main import conversar, montar_agente


class LLMFalso:
    """Devolve respostas roteirizadas, na ordem das chamadas."""
    def __init__(self, *respostas: str):
        self._respostas = list(respostas)

    def complete(self, messages, tools=None) -> LLMResponse:
        return LLMResponse(content=self._respostas.pop(0))


class RetrieverFalso:
    def search(self, question: str):
        return []


def _agente(*respostas: str):
    # repos = objeto qualquer: Ferramentas só o guarda; esta rota não chega às ferramentas.
    return montar_agente(llm=LLMFalso(*respostas), repos=object(), retriever=RetrieverFalso())


def test_saudacao_passa_pelo_grafo_inteiro():
    agente = _agente("social", "Oi! Como posso te ajudar? 🎸")
    assert agente.responder("oi") == "Oi! Como posso te ajudar? 🎸"
    assert len(agente.historico("default")) == 2  # usuário + resposta validada


def test_cli_conversa_e_grava_transcricao(tmp_path: Path):
    agente = _agente("social", "Oi! Tudo bem?")
    entradas = iter(["oi", "", "sair"])
    saidas: list[str] = []
    destino = tmp_path / "conversa.md"

    conversar(agente, entrada=lambda _: next(entradas), saida=saidas.append, salvar=destino)

    assert any("Agente: Oi! Tudo bem?" in s for s in saidas)
    texto = destino.read_text(encoding="utf-8")
    assert "**Cliente:** oi" in texto and "**Agente:** Oi! Tudo bem?" in texto


def test_cli_encerra_com_ctrl_d():
    def entrada(_):
        raise EOFError
    conversar(_agente(), entrada=entrada, saida=lambda _: None)  # não deve levantar