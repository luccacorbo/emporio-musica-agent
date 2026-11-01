"""Carrega os CSVs com Pandas e confere o básico (colunas, tipos, ausentes, integridade)."""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

# tabela -> (arquivo, colunas obrigatórias)
TABLES = {
    "categories": ("categories.csv", ["category_id", "name"]),
    "customers": ("customers.csv", ["customer_id", "name"]),
    "products": ("products.csv", ["product_id", "name", "price_brl", "category_id", "stock_quantity", "status"]),
    "orders": ("orders.csv", ["order_id", "customer_id", "status", "total_brl"]),
    "order_items": ("order_items.csv", ["order_id", "product_id", "quantity"]),
    "promotions": ("promotions.csv", ["promotion_id", "product_id", "discount_percent"]),
}

NUMERIC_COLUMNS = ["price_brl", "total_brl", "discount_percent", "stock_quantity", "quantity"]
DATE_COLUMNS = ["order_date", "estimated_delivery", "created_at"]

# (tabela filha, coluna, tabela pai, coluna) para checar chaves estrangeiras
FOREIGN_KEYS = [
    ("products", "category_id", "categories", "category_id"),
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("promotions", "product_id", "products", "product_id"),
]


class DataError(Exception):
    """Arquivo ou coluna obrigatória ausente: não dá para continuar."""


def load_tables(data_dir: Path | str = DATA_DIR) -> dict[str, pd.DataFrame]:
    """Lê os CSVs. IDs e telefones ficam como texto; números e datas são convertidos."""
    tables = {}
    for name, (filename, required) in TABLES.items():
        path = Path(data_dir) / filename
        if not path.exists():
            raise DataError(f"Arquivo não encontrado: {path}")

        df = pd.read_csv(path, dtype=str)
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise DataError(f"{filename}: colunas ausentes {missing}")

        for col in df.columns:
            if col in NUMERIC_COLUMNS:
                df[col] = pd.to_numeric(df[col], errors="coerce")  # inválido vira NaN
            elif col in DATE_COLUMNS:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        if "is_active" in df.columns:
            df["is_active"] = df["is_active"].str.strip().str.lower().isin(["true", "1", "sim"])
        tables[name] = df
    return tables


def check_data(tables: dict[str, pd.DataFrame]) -> list[str]:
    """Devolve uma lista de avisos (vazia = dados ok). Não altera os dados."""
    warnings = []
    for name, (_, required) in TABLES.items():
        df = tables[name]
        nulls = int(df[required].isna().any(axis=1).sum())
        if nulls:
            warnings.append(f"{name}: {nulls} linha(s) com valor ausente/inválido em {required}")
        key = required[0]
        dups = int(df[key].duplicated().sum()) if name != "order_items" else 0
        if dups:
            warnings.append(f"{name}: {dups} id(s) duplicado(s) em '{key}'")
    for child, col, parent, parent_col in FOREIGN_KEYS:
        orphans = int((~tables[child][col].isin(tables[parent][parent_col])).sum())
        if orphans:
            warnings.append(f"{child}.{col}: {orphans} valor(es) sem correspondente em {parent}.{parent_col}")
    return warnings