"""Garante a regra de arquitetura: só `src/integrations/` conhece frameworks de IA.

Também confere o sentido das dependências: as camadas de domínio (data, models, rag,
tools, ...) nunca importam `src.integrations`; quem liga as peças é o `main.py`.
"""

import ast
from pathlib import Path

import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "src").is_dir())
SRC = ROOT / "src"

FORBIDDEN_ROOTS = {"langgraph", "chromadb", "sentence_transformers", "transformers", "huggingface_hub", "torch"}


def imported_modules(path: Path) -> set[str]:
    """Nomes completos dos módulos importados por um arquivo (import x / from x import y)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


def is_framework(module: str) -> bool:
    root = module.split(".")[0]
    return root.startswith("langchain") or root in FORBIDDEN_ROOTS


def files_outside_integrations() -> list[Path]:
    return [p for p in SRC.rglob("*.py") if "integrations" not in p.relative_to(SRC).parts and p.name != "main.py"]


@pytest.mark.parametrize("path", files_outside_integrations(), ids=lambda p: str(p.relative_to(SRC)))
def test_only_integrations_import_ai_frameworks(path):
    offenders = sorted(m for m in imported_modules(path) if is_framework(m))
    assert not offenders, f"{path.relative_to(ROOT)} importa framework fora de src/integrations: {offenders}"


@pytest.mark.parametrize("path", files_outside_integrations(), ids=lambda p: str(p.relative_to(SRC)))
def test_domain_layers_do_not_import_integrations(path):
    offenders = sorted(m for m in imported_modules(path) if m.startswith("src.integrations"))
    assert not offenders, f"{path.relative_to(ROOT)} depende de src.integrations: {offenders}"


def test_architecture_test_detects_violations(tmp_path):
    """Sanidade do próprio teste: ele precisa enxergar um import proibido."""
    bad = tmp_path / "bad.py"
    bad.write_text("import langchain_core\nfrom langgraph.graph import StateGraph\nimport pandas\n")

    assert sorted(m for m in imported_modules(bad) if is_framework(m)) == ["langchain_core", "langgraph.graph"]