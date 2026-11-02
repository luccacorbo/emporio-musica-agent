import pytest

from src.agent.rotas import interpretar_rota


@pytest.mark.parametrize("texto, esperado", [
    ("da_loja", "da_loja"),
    ("  Social\n", "social"),
    ("reclamação", "reclamacao"),
    ("fora do escopo", "fora_do_escopo"),
    ("A rota é fora_do_escopo.", "fora_do_escopo"),
    ("social, mas também da_loja", "social"),     # vale a primeira citada
    ("não sei dizer", "da_loja"),                  # irreconhecível: cai no padrão
    ("", "da_loja"),
])
def test_interpretar_rota(texto, esperado):
    assert interpretar_rota(texto) == esperado