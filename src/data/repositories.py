"""Repositories: consultas sobre os dados, devolvendo modelos Pydantic.

Não levantam erro quando algo não existe: devolvem None ou lista vazia
(quem decide o que dizer ao cliente é a tool / o agente).
"""

import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import pandas as pd
from pydantic import BaseModel, ValidationError

from src.data.loader import DATA_DIR, check_data, load_tables
from src.models import Category, Customer, Order, OrderItem, PricedProduct, Product, Promotion
from src.models.catalog import PIX_DISCOUNT_PERCENT

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def normalize(text: str) -> str:
    """Minúsculas e sem acento: 'Violões' -> 'violoes'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def to_models(df: pd.DataFrame, model: type[T]) -> list[T]:
    """Converte linhas em modelos Pydantic; linhas inválidas são ignoradas e logadas."""
    rows = df.astype(object).where(df.notna(), None).to_dict("records")
    result = []
    for row in rows:
        try:
            result.append(model.model_validate(row))
        except ValidationError as err:
            logger.warning("Linha inválida em %s ignorada: %s", model.__name__, err.errors()[0]["msg"])
    return result


class ProductRepository:
    def __init__(self, products: list[Product], categories: list[Category], promotions: list[Promotion]):
        self._products = {p.product_id: p for p in products}
        self._categories = {c.category_id: c for c in categories}
        self._promotions = promotions

    def list_categories(self) -> list[Category]:
        return sorted(self._categories.values(), key=lambda c: c.name)

    def get(self, product_id: str) -> Product | None:
        return self._products.get(product_id)

    def get_priced(self, product_id: str) -> PricedProduct | None:
        product = self.get(product_id)
        return self._price(product) if product else None

    def _price(self, product: Product) -> PricedProduct:
        # Promoções não são cumulativas: se houver mais de uma ativa, vale a maior.
        active = [p.discount_percent for p in self._promotions if p.product_id == product.product_id and p.is_active]
        discount = max(active, default=0.0)
        final = round(product.price_brl * (1 - discount / 100), 2)
        # Desconto PIX não vale sobre preço promocional (manual §6.2).
        pix = None if discount else round(product.price_brl * (1 - PIX_DISCOUNT_PERCENT / 100), 2)
        return PricedProduct(
            product=product, list_price=product.price_brl, discount_percent=discount, final_price=final, pix_price=pix
        )

    def search(
        self,
        query: str | None = None,
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        only_available: bool = True,
        limit: int = 10,
    ) -> list[PricedProduct]:
        """Busca por texto (nome/descrição), categoria e faixa de preço final.

        Sem acento e sem diferença de maiúsculas. Todas as palavras da consulta
        precisam aparecer. Resultado ordenado do mais barato ao mais caro.
        """
        products = list(self._products.values())

        if category:
            wanted = normalize(category)
            ids = {c.category_id for c in self._categories.values() if wanted in normalize(c.name) or wanted == c.category_id.lower()}
            products = [p for p in products if p.category_id in ids]

        if query:
            words = normalize(query).split()
            products = [p for p in products if all(w in normalize(f"{p.name} {p.description or ''}") for w in words)]

        if only_available:
            products = [p for p in products if p.is_available]

        priced = [self._price(p) for p in products]
        if min_price is not None:
            priced = [p for p in priced if p.final_price >= min_price]
        if max_price is not None:
            priced = [p for p in priced if p.final_price <= max_price]

        return sorted(priced, key=lambda p: p.final_price)[:limit]

    def suggest_alternatives(self, product_id: str, limit: int = 3) -> list[PricedProduct]:
        """Produtos disponíveis da mesma categoria, do preço mais próximo ao mais distante (manual §7.3)."""
        ref = self.get_priced(product_id)
        if ref is None:
            return []
        others = [
            self._price(p) for p in self._products.values()
            if p.category_id == ref.product.category_id and p.product_id != product_id and p.is_available
        ]
        return sorted(others, key=lambda p: abs(p.final_price - ref.final_price))[:limit]


class CustomerRepository:
    def __init__(self, customers: list[Customer]):
        self._customers = {c.customer_id: c for c in customers}

    def get(self, customer_id: str) -> Customer | None:
        return self._customers.get(customer_id)

    def find_by_email(self, email: str) -> Customer | None:
        return next((c for c in self._customers.values() if c.email and c.email.lower() == email.strip().lower()), None)

    def find_by_phone(self, phone: str) -> Customer | None:
        digits = "".join(ch for ch in phone if ch.isdigit())
        if not digits:
            return None
        return next((c for c in self._customers.values() if c.phone and "".join(ch for ch in c.phone if ch.isdigit()) == digits), None)


class OrderRepository:
    def __init__(self, orders: list[Order], items: list[OrderItem]):
        self._orders = {o.order_id: o for o in orders}
        self._items = items

    def get(self, order_id: str) -> Order | None:
        return self._orders.get(order_id.strip())

    def list_by_customer(self, customer_id: str) -> list[Order]:
        """Pedidos do cliente, do mais recente ao mais antigo."""
        orders = [o for o in self._orders.values() if o.customer_id == customer_id]
        return sorted(orders, key=lambda o: o.order_date or pd.Timestamp.min, reverse=True)

    def find_by_tracking_code(self, code: str) -> Order | None:
        return next((o for o in self._orders.values() if o.tracking_code and o.tracking_code.upper() == code.strip().upper()), None)

    def get_items(self, order_id: str) -> list[OrderItem]:
        return [i for i in self._items if i.order_id == order_id.strip()]


@dataclass
class Repositories:
    products: ProductRepository
    customers: CustomerRepository
    orders: OrderRepository
    warnings: list[str]  # problemas encontrados nos dados (ver check_data)


def build_repositories(data_dir: Path | str = DATA_DIR) -> Repositories:
    """Carrega os CSVs e monta todos os repositories."""
    tables = load_tables(data_dir)
    warnings = check_data(tables)
    for w in warnings:
        logger.warning(w)
    return Repositories(
        products=ProductRepository(
            to_models(tables["products"], Product),
            to_models(tables["categories"], Category),
            to_models(tables["promotions"], Promotion),
        ),
        customers=CustomerRepository(to_models(tables["customers"], Customer)),
        orders=OrderRepository(to_models(tables["orders"], Order), to_models(tables["order_items"], OrderItem)),
        warnings=warnings,
    )
