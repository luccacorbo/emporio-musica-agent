import pytest
from pydantic import ValidationError

from src.tools.orders import NAO_ENCONTRADO, ConsultaPedidoInput, consultar_pedido


def _consulta(repos, numero, email):
    return consultar_pedido(repos, ConsultaPedidoInput(numero_pedido=numero, email=email))


def test_pedido_com_email_correto(fake_repos):
    r = _consulta(fake_repos, "1001", "ana@exemplo.com")
    assert r.encontrado
    assert r.pedido.status == "confirmed"
    assert r.pedido.total_texto == "R$ 900,00"
    assert r.pedido.forma_pagamento == "Cartão de crédito em 6x"
    assert r.pedido.itens[0].produto == "Violão Yamaha F310"


def test_email_sem_distincao_de_caixa(fake_repos):
    assert _consulta(fake_repos, "1001", "ANA@Exemplo.com").encontrado


def test_numero_com_hash(fake_repos):
    assert _consulta(fake_repos, "#1001", "ana@exemplo.com").encontrado


def test_email_de_outro_cliente_nao_revela_o_pedido(fake_repos):
    r = _consulta(fake_repos, "1001", "bruno@exemplo.com")
    assert not r.encontrado and r.pedido is None
    assert r.mensagem == NAO_ENCONTRADO


def test_pedido_inexistente_tem_a_mesma_resposta_de_email_errado(fake_repos):
    inexistente = _consulta(fake_repos, "9999", "ana@exemplo.com")
    email_errado = _consulta(fake_repos, "1001", "bruno@exemplo.com")
    assert inexistente == email_errado


def test_pedido_sem_rastreio_explica_quando_sai_o_codigo(fake_repos):
    p = _consulta(fake_repos, "1001", "ana@exemplo.com").pedido
    assert p.codigo_rastreio is None and "despachado" in p.aviso_rastreio


def test_pedido_despachado_traz_codigo(fake_repos):
    p = _consulta(fake_repos, "1002", "bruno@exemplo.com").pedido
    assert p.codigo_rastreio == "BR4K7M2X9P1BR" and p.aviso_rastreio is None


@pytest.mark.parametrize("email", ["", "sem-arroba", "a@"])
def test_email_invalido_e_rejeitado(email):
    with pytest.raises(ValidationError):
        ConsultaPedidoInput(numero_pedido="1001", email=email)