"""Mini-dataset de teste (mesmo schema dos CSVs reais), gravado em uma pasta temporária."""

import pytest

from src.data.repositories import build_repositories

CSVS = {
    "categories.csv": """category_id,name,description
CAT1,Violões,Violões acústicos
CAT2,Guitarras,Guitarras elétricas
""",
    "customers.csv": """customer_id,name,phone,email,city
C1,Ana Souza,(67) 99999-1234,ana@example.com,Campo Grande
C2,Bruno Lima,67988887777,bruno@example.com,Dourados
""",
    "products.csv": """product_id,price_brl,name,category_id,description,stock_quantity,status,specs,created_at
P1,1999.00,Takamine GD20,CAT1,Violão eletroacústico,5,active,,2024-05-10
P2,899.00,Tagima Dallas,CAT1,Violão folk,3,active,,2024-06-01
P3,650.00,Giannini Start,CAT1,Violão de entrada,0,active,,2023-01-15
P4,4500.00,Fender Stratocaster,CAT2,Guitarra elétrica,2,active,,2024-02-02
P5,500.00,Phoenix Antigo,CAT1,Violão antigo,2,discontinued,,2020-01-01
""",
    "promotions.csv": """promotion_id,product_id,discount_percent,description,is_active
PR1,P2,10,Semana do Músico,true
PR2,P1,20,Promoção encerrada,false
""",
    "orders.csv": """order_id,customer_id,order_date,status,total_brl,payment_method,tracking_code,estimated_delivery,notes
O1,C1,2025-03-10,delivered,1999.00,pix,BR4K7M2X9P1BR,2025-03-15,
O2,C1,2025-04-02,processing,809.10,credit_card,,2025-04-06,
O3,C2,2025-03-20,shipped,4500.00,credit_card,BR9A8B7C6D5BR,2025-03-25,
""",
    "order_items.csv": """order_id,quantity,product_id
O1,1,P1
O2,1,P2
O3,1,P4
""",
}


@pytest.fixture
def write_csvs(tmp_path):
    """Fábrica: grava os CSVs de teste em tmp_path e devolve a pasta.

    `overrides` troca o conteúdo de um arquivo, ex.: write_csvs(products_csv="...").
    """

    def _write(**overrides):
        contents = {**CSVS, **{k.replace("_csv", ".csv"): v for k, v in overrides.items()}}
        for filename, text in contents.items():
            (tmp_path / filename).write_text(text, encoding="utf-8")
        return tmp_path

    return _write


@pytest.fixture
def data_dir(write_csvs):
    return write_csvs()


@pytest.fixture
def repos(data_dir):
    return build_repositories(data_dir)