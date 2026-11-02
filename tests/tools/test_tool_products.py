import pytest
from pydantic import ValidationError

from src.tools.products import (
    BuscaProdutoInput, DisponibilidadeInput, buscar_produto, consultar_disponibilidade,
)
from src.data.repositories import build_repositories
from src.tools.products import *

repos = build_repositories()
print(buscar_produto(repos, BuscaProdutoInput(categoria="Violões", preco_max=1000)).model_dump_json(indent=2))
print(buscar_produto(repos, BuscaProdutoInput(termo="Takamine GD20")).produtos[0].preco_texto)

def test_preco_promocional_mostra_original_percentual_e_final(fake_repos):
    r = buscar_produto(fake_repos, BuscaProdutoInput(termo="Takamine"))
    p = r.produtos[0]
    assert "R$ 3.000,00" in p.preco_texto and "R$ 2.700,00" in p.preco_texto
    assert "10% de desconto" in p.preco_texto
    assert p.preco_pix is None


def test_preco_sem_promocao_mostra_pix(fake_repos):
    p = buscar_produto(fake_repos, BuscaProdutoInput(termo="Yamaha")).produtos[0]
    assert "R$ 900,00" in p.preco_texto and "R$ 855,00 no PIX" in p.preco_texto


def test_somente_disponiveis_exclui_descontinuado_e_sem_estoque(fake_repos):
    r = buscar_produto(fake_repos, BuscaProdutoInput(termo="violão"))
    assert {p.product_id for p in r.produtos} == {"P1", "P2"}
    assert r.aviso is None


def test_sem_disponiveis_mostra_indisponiveis_com_aviso(fake_repos):
    r = buscar_produto(fake_repos, BuscaProdutoInput(termo="antigo"))
    assert [p.situacao for p in r.produtos] == ["descontinuado"]
    assert "indisponíveis" in r.aviso


def test_nada_encontrado_tem_aviso(fake_repos):
    r = buscar_produto(fake_repos, BuscaProdutoInput(termo="saxofone"))
    assert r.produtos == [] and r.aviso


def test_categoria_singular_nao_resolve_e_lista_categorias(fake_repos):
    r = buscar_produto(fake_repos, BuscaProdutoInput(categoria="violão"))
    assert r.produtos == [] and "Violões" in r.aviso
    assert fake_repos.products.calls == []  # nem chegou a buscar


def test_categoria_valida_e_passada_com_nome_exato(fake_repos):
    buscar_produto(fake_repos, BuscaProdutoInput(categoria="violões baratos"))
    assert fake_repos.products.calls[0]["category"] == "Violões"


def test_busca_exige_algum_filtro():
    with pytest.raises(ValidationError):
        BuscaProdutoInput()


def test_faixa_de_preco_invalida():
    with pytest.raises(ValidationError):
        BuscaProdutoInput(preco_min=500, preco_max=100)


def test_disponibilidade_de_produto_disponivel_nao_traz_alternativas(fake_repos):
    r = consultar_disponibilidade(fake_repos, DisponibilidadeInput(product_id="P1"))
    assert r.encontrado and r.produto.situacao == "disponivel" and r.produto.estoque == 5
    assert r.alternativas == []


@pytest.mark.parametrize("pid,situacao", [("P3", "descontinuado"), ("P4", "sem_estoque"), ("P5", "em_breve")])
def test_indisponivel_traz_alternativas_disponiveis(fake_repos, pid, situacao):
    r = consultar_disponibilidade(fake_repos, DisponibilidadeInput(product_id=pid))
    assert r.produto.situacao == situacao
    assert r.alternativas and all(a.situacao == "disponivel" for a in r.alternativas)


def test_disponibilidade_de_produto_inexistente(fake_repos):
    r = consultar_disponibilidade(fake_repos, DisponibilidadeInput(product_id="XXX"))
    assert not r.encontrado and r.produto is None and r.mensagem