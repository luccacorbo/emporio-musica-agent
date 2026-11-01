"""Testes do loader e da validação dos modelos."""

import pandas as pd
import pytest
from pydantic import ValidationError

from src.data.loader import DATA_DIR, DataError, check_data, load_tables
from src.data.repositories import build_repositories
from src.models import Product, Promotion


def test_loads_all_tables_without_warnings(data_dir):
    tables = load_tables(data_dir)

    assert {k: len(v) for k, v in tables.items()} == {
        "categories": 2, "customers": 2, "products": 5, "orders": 3, "order_items": 3, "promotions": 2,
    }
    assert check_data(tables) == []


def test_types_are_converted(data_dir):
    tables = load_tables(data_dir)

    assert tables["products"]["price_brl"].dtype == "float64"
    assert pd.api.types.is_datetime64_any_dtype(tables["orders"]["order_date"])
    assert tables["promotions"]["is_active"].tolist() == [True, False]


def test_missing_file_raises(data_dir):
    (data_dir / "customers.csv").unlink()
    with pytest.raises(DataError, match="customers.csv"):
        load_tables(data_dir)


def test_missing_required_column_raises(write_csvs):
    tmp_path = write_csvs(products_csv="product_id,name\nP1,Violão\n")
    with pytest.raises(DataError, match="price_brl"):
        load_tables(tmp_path)


def test_check_data_reports_missing_duplicates_and_orphans(write_csvs):
    tmp_path = write_csvs(
        categories_csv="category_id,name,description\nCAT1,Violões,\nCAT1,Violões 2,\n",   # id duplicado
        products_csv=(
            "product_id,price_brl,name,category_id,description,stock_quantity,status,specs,created_at\n"
            "P1,abc,Violão,CAT1,,2,active,,\n"      # preço inválido
            "P2,100,Violão B,CAT9,,2,active,,\n"    # categoria inexistente
        ),
    )
    warnings = " | ".join(check_data(load_tables(tmp_path)))

    assert "products: 1 linha(s)" in warnings
    assert "duplicado" in warnings
    assert "products.category_id" in warnings


def test_invalid_rows_are_skipped_by_repositories(write_csvs):
    tmp_path = write_csvs(
        products_csv=(
            "product_id,price_brl,name,category_id,description,stock_quantity,status,specs,created_at\n"
            "P1,abc,Preço inválido,CAT1,,2,active,,\n"
            "P2,100,Estoque negativo,CAT1,,-1,active,,\n"
            "P3,100,Ok,CAT1,,2,active,,\n"
        ),
    )
    repos = build_repositories(tmp_path)

    assert repos.products.get("P1") is None
    assert repos.products.get("P2") is None
    assert repos.products.get("P3") is not None
    assert repos.warnings  # o problema foi reportado


def test_models_reject_invalid_values():
    base = dict(product_id="1", name="X", category_id="C", stock_quantity=1, status="active")
    with pytest.raises(ValidationError):
        Product(price_brl=0, **base)
    with pytest.raises(ValidationError):
        Promotion(promotion_id="1", product_id="1", discount_percent=150)


def test_product_availability():
    base = dict(product_id="1", name="X", price_brl=10, category_id="C")
    assert Product(stock_quantity=1, status="active", **base).is_available
    assert not Product(stock_quantity=0, status="active", **base).is_available
    assert not Product(stock_quantity=1, status="Discontinued", **base).is_available
    assert not Product(stock_quantity=1, status="coming_soon", **base).is_available


@pytest.mark.skipif(not (DATA_DIR / "products.csv").exists(), reason="CSVs reais não estão em data/raw")
def test_real_data_has_no_warnings():
    """Smoke test com os CSVs reais (roda só se estiverem em data/raw)."""
    assert check_data(load_tables()) == []