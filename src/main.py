"""Raiz de composição e CLI: liga dados, RAG, ferramentas, LLM e grafo.

    python -m src.main                      # conversa no terminal
    python -m src.main --salvar examples/c1.md   # também grava a conversa em Markdown
    python -m src.main --mermaid            # imprime o diagrama do grafo (para o README)
"""
import argparse
import logging
import sys
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from src.agent.llm import GroqLLMClient, LLMClient, LLMError
from src.agent.prompts import MENSAGEM_ERRO
from src.data.loader import DataError
from src.data.repositories import Repositories, build_repositories
from src.integrations.langchain.retriever import build_policy_retriever
from src.integrations.langgraph.graph import Agente, criar_agente
from src.rag.document_loader import DocumentError
from src.tools.policies import PolicyRetriever
from src.tools.registry import Ferramentas

log = logging.getLogger(__name__)

CONVERSA_ID = "cli"
COMANDOS_SAIDA = {"sair", "exit", "quit"}


def montar_agente(llm: LLMClient | None = None,
                  repos: Repositories | None = None,
                  retriever: PolicyRetriever | None = None) -> Agente:
    """Cria as dependências que não vieram de fora e as injeta no agente."""
    repos = repos if repos is not None else build_repositories()
    retriever = retriever if retriever is not None else build_policy_retriever()
    llm = llm if llm is not None else GroqLLMClient()
    return criar_agente(llm, Ferramentas(repos, retriever))


def _gravar(caminho: Path | None, cliente: str, agente: str) -> None:
    if caminho is None:
        return
    with caminho.open("a", encoding="utf-8") as f:
        f.write(f"**Cliente:** {cliente}\n\n**Agente:** {agente}\n\n")


def conversar(agente: Agente, entrada: Callable[[str], str] = input,
              saida: Callable[[str], None] = print, salvar: Path | None = None) -> None:
    """Loop de terminal. `entrada`/`saida` são injetáveis para teste."""
    saida("Empório da Música: atendimento. Digite 'sair' para encerrar.\n")
    while True:
        try:
            texto = entrada("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            saida("")
            break
        if texto.lower() in COMANDOS_SAIDA:
            break
        if not texto:
            continue
        try:
            resposta = agente.responder(texto, CONVERSA_ID)
        except Exception:  # um erro inesperado não derruba a sessão
            log.exception("Falha inesperada no turno")
            resposta = MENSAGEM_ERRO
        saida(f"Agente: {resposta}\n")
        _gravar(salvar, texto, resposta)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agente de atendimento da Empório da Música")
    parser.add_argument("--api", action="store_true", help="sobe a API + interface web")
    parser.add_argument("--porta", type=int, default=8000, help="porta da API (padrão 8000)")
    parser.add_argument("--salvar", type=Path, help="grava a conversa neste arquivo .md")
    parser.add_argument("--mermaid", action="store_true", help="imprime o diagrama do grafo e sai")
    parser.add_argument("-v", "--verbose", action="store_true", help="logs detalhados")
    args = parser.parse_args(argv)

    load_dotenv()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="[%(name)s] %(message)s")

    if args.api:
        import uvicorn  # import tardio: o CLI não precisa dele
        uvicorn.run("src.api.app:app", host="127.0.0.1", port=args.porta)
        return 0

    try:
        agente = montar_agente()
    except (DataError, DocumentError, LLMError) as erro:
        print(f"Não foi possível iniciar: {erro}", file=sys.stderr)
        return 1

    if args.mermaid:
        print(agente.mermaid())
        return 0

    if args.salvar:
        args.salvar.parent.mkdir(parents=True, exist_ok=True)
    conversar(agente, salvar=args.salvar)
    return 0


if __name__ == "__main__":
    sys.exit(main())