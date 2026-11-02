"""API do chat e servidor do front. `criar_app` aceita um agente injetado (testes)."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from src.agent.prompts import MENSAGEM_ERRO
from src.api.schemas import ChatRequest, ChatResponse
from src.main import montar_agente

log = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


class Respondedor(Protocol):
    """Contrato mínimo do agente (a implementação fica em integrations/)."""
    def responder(self, mensagem: str, conversa_id: str = "default") -> str: ...


def criar_app(agente: Respondedor | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Sem agente injetado, monta o real na subida (carrega dados, índice e modelo de embeddings).
        if app.state.agente is None:
            app.state.agente = montar_agente()
        yield

    app = FastAPI(title="Empório da Música: atendimento", lifespan=lifespan)
    app.state.agente = agente

    @app.get("/api/saude")
    def saude() -> dict[str, str]:
        return {"status": "ok"}

    # `def` (e não `async def`): o agente é síncrono e bloqueia em chamadas ao LLM.
    # O FastAPI roda funções `def` numa thread, sem travar o servidor.
    @app.post("/api/chat", response_model=ChatResponse)
    def chat(req: ChatRequest, request: Request) -> ChatResponse:
        try:
            resposta = request.app.state.agente.responder(req.mensagem, req.conversa_id)
        except Exception:
            log.exception("Falha no turno (conversa %s)", req.conversa_id)
            raise HTTPException(status_code=500, detail=MENSAGEM_ERRO)
        return ChatResponse(resposta=resposta, conversa_id=req.conversa_id)

    # Montado por último: as rotas /api/* têm prioridade sobre os arquivos estáticos.
    if FRONTEND_DIR.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


app = criar_app()  # usado por: uvicorn src.api.app:app