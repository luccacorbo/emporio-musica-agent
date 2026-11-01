"""Testes das consultas de produtos, preços e promoções."""

import pytest


def names(results):
    return [r.product.name for r in results]


# --- preço -------------------------------------------------------------------
def test_price_without_promotion_has_pix_discount(repos):
    p = repos.products.get_priced("P1")  # Takamine GD20

    assert p.list_price == 1999.00
    assert p.final_price == 1999.00
    assert p.pix_price == 1899.05  # 5% de desconto


def test_price_with_active_promotion(repos):
    p = repos.products.get_priced("P2")

    assert p.discount_percent == 10
    assert p.final_price == pytest.approx(809.10)
    assert p.pix_price is None  # PIX não acumula com promoção


def test_inactive_promotion_is_ignored(repos):
    p = repos.products.get_priced("P1")  # PR2 existe mas está inativa
    assert p.discount_percent == 0


def test_unknown_product(repos):
    assert repos.products.get_priced("NOPE") is None


# --- busca -------------------------------------------------------------------
def test_search_by_name(repos):
    assert names(repos.products.search(query="Takamine GD20")) == ["Takamine GD20"]


def test_search_ignores_case_and_accent(repos):
    assert names(repos.products.search(query="VIOLÃO FOLK")) == ["Tagima Dallas"]


def test_search_requires_all_words(repos):
    assert repos.products.search(query="takamine fender") == []


def test_search_by_category_excludes_unavailable(repos):
    # P3 (sem estoque) e P5 (descontinuado) ficam de fora
    assert names(repos.products.search(category="violões")) == ["Tagima Dallas", "Takamine GD20"]


def test_search_include_unavailable(repos):
    assert len(repos.products.search(category="violões", only_available=False)) == 4


def test_search_unknown_category(repos):
    assert repos.products.search(category="saxofone") == []


def test_max_price_uses_final_price(repos):
    # Exemplo do enunciado: "violões até R$ 1000". Tagima: 899 -> 809,10 com promoção.
    assert names(repos.products.search(category="violões", max_price=1000)) == ["Tagima Dallas"]
    assert repos.products.search(category="violões", max_price=800) == []


def test_min_price(repos):
    assert names(repos.products.search(category="violões", min_price=1000)) == ["Takamine GD20"]


def test_results_sorted_by_price_and_limited(repos):
    prices = [p.final_price for p in repos.products.search()]
    assert prices == sorted(prices)
    assert len(repos.products.search(limit=1)) == 1


# --- alternativas e categorias -----------------------------------------------
def test_alternatives_for_out_of_stock_product(repos):
    # P3 (R$ 650, sem estoque): sugere violões disponíveis, mais próximos em preço primeiro
    assert names(repos.products.suggest_alternatives("P3")) == ["Tagima Dallas", "Takamine GD20"]


def test_alternatives_unknown_product(repos):
    assert repos.products.suggest_alternatives("NOPE") == []


def test_list_categories(repos):
    assert [c.name for c in repos.products.list_categories()] == ["Guitarras", "Violões"]
