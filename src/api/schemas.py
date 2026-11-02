"""Contrato HTTP do chat."""
from pydantic import BaseModel, Field

# O limite real de tamanho (1000 caracteres) é do guardrail de entrada, que responde no tom da loja.
# Aqui só barramos payloads absurdos.
MAX_BYTES_MENSAGEM = 5000


class ChatRequest(BaseModel):
    mensagem: str = Field(max_length=MAX_BYTES_MENSAGEM)
    conversa_id: str = Field(pattern=r"^[\w-]{8,64}$", description="Gerado pelo navegador (UUID).")


class ChatResponse(BaseModel):
    resposta: str
    conversa_id: str