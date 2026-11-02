"""A API repassa a mensagem ao agente, valida o contrato e traduz falhas em erro amigável."""
from fastapi.testclient import TestClient

from src.api.app import criar_app
from src.agent.prompts import MENSAGEM_ERRO

ID = "conversa-1234"


class AgenteFalso:
    def __init__(self):
        self.chamadas: list[tuple[str, str]] = []

    def responder(self, mensagem: str, conversa_id: str = "default") -> str:
        self.chamadas.append((mensagem, conversa_id))
        return f"eco: {mensagem}"


class AgenteQuebrado:
    def responder(self, mensagem: str, conversa_id: str = "default") -> str:
        raise RuntimeError("boom")


def test_chat_repassa_mensagem_e_conversa_id():
    agente = AgenteFalso()
    client = TestClient(criar_app(agente))
    r = client.post("/api/chat", json={"mensagem": "oi", "conversa_id": ID})
    assert r.status_code == 200
    assert r.json() == {"resposta": "eco: oi", "conversa_id": ID}
    assert agente.chamadas == [("oi", ID)]


def test_conversa_id_invalido_e_rejeitado():
    client = TestClient(criar_app(AgenteFalso()))
    r = client.post("/api/chat", json={"mensagem": "oi", "conversa_id": "../etc"})
    assert r.status_code == 422


def test_mensagem_ausente_e_rejeitada():
    client = TestClient(criar_app(AgenteFalso()))
    assert client.post("/api/chat", json={"conversa_id": ID}).status_code == 422


def test_falha_inesperada_vira_500_com_mensagem_amigavel():
    client = TestClient(criar_app(AgenteQuebrado()))
    r = client.post("/api/chat", json={"mensagem": "oi", "conversa_id": ID})
    assert r.status_code == 500
    assert r.json()["detail"] == MENSAGEM_ERRO


def test_saude():
    client = TestClient(criar_app(AgenteFalso()))
    assert client.get("/api/saude").json() == {"status": "ok"}


def test_serve_a_interface():
    client = TestClient(criar_app(AgenteFalso()))
    r = client.get("/")
    assert r.status_code == 200 and "Empório da Música" in r.text