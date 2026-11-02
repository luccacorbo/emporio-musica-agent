from types import SimpleNamespace as NS

import pytest

from src.tools.common import normalizar


def _priced(pid, nome, preco, *, cat="C1", status="active", estoque=5,
            desconto=0.0, final=None, pix=None):
    produto = NS(product_id=pid, name=nome, category_id=cat, description=f"{nome} - descrição",
                 stock_quantity=estoque, status=status, specs="{}",
                 is_available=(status == "active" and estoque > 0))
    return NS(product=produto, list_price=preco, discount_percent=desconto,
              final_price=preco if final is None else final, pix_price=pix)


class FakeProducts:
    def __init__(self):
        self.calls = []
        self.priced = [
            _priced("P1", "Violão Yamaha F310", 900.0, pix=855.0),
            _priced("P2", "Violão Takamine GD20", 3000.0, desconto=10.0, final=2700.0),
            _priced("P3", "Violão Antigo", 500.0, status="discontinued"),
            _priced("P4", "Guitarra Fender Squier", 2500.0, cat="C2", estoque=0),
            _priced("P5", "Ukulele Kala", 400.0, cat="C3", status="coming_soon"),
        ]
        self.categories = [NS(category_id="C1", name="Violões"),
                           NS(category_id="C2", name="Guitarras"),
                           NS(category_id="C3", name="Ukuleles")]

    def list_categories(self):
        return self.categories

    def get(self, pid):
        priced = self.get_priced(pid)
        return priced.product if priced else None

    def get_priced(self, pid):
        return next((p for p in self.priced if p.product.product_id == pid), None)

    def search(self, query=None, category=None, min_price=None, max_price=None,
               only_available=True, limit=10):
        self.calls.append(dict(query=query, category=category, only_available=only_available))
        achados = [p for p in self.priced if p.product.is_available or not only_available]
        if query:
            achados = [p for p in achados if normalizar(query) in normalizar(p.product.name)]
        return achados[:limit]

    def suggest_alternatives(self, pid, limit=3):
        return [p for p in self.priced if p.product.is_available and p.product.product_id != pid][:limit]


class FakeOrders:
    def __init__(self):
        self.orders = {
            "1001": NS(order_id="1001", customer_id="C1", order_date="2025-06-10", status="confirmed",
                       total_brl=900.0, payment_method="credit_6x", tracking_code=None,
                       estimated_delivery=None, notes=None),
            "1002": NS(order_id="1002", customer_id="C2", order_date="2025-06-02", status="shipped",
                       total_brl=2700.0, payment_method="pix", tracking_code="BR4K7M2X9P1BR",
                       estimated_delivery="2025-06-12", notes=None),
        }

    def get(self, order_id):
        return self.orders.get(order_id)

    def get_items(self, order_id):
        return [NS(product_id="P1" if order_id == "1001" else "P2", quantity=1)]


class FakeCustomers:
    def __init__(self):
        self.customers = {"C1": NS(customer_id="C1", email="ana@exemplo.com"),
                          "C2": NS(customer_id="C2", email="bruno@exemplo.com")}

    def get(self, cid):
        return self.customers.get(cid)


@pytest.fixture
def fake_repos():
    return NS(products=FakeProducts(), orders=FakeOrders(), customers=FakeCustomers())