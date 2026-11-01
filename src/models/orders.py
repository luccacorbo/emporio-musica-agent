"""Modelos de clientes e pedidos."""

from datetime import datetime

from pydantic import BaseModel, Field


class Customer(BaseModel):
    customer_id: str
    name: str
    phone: str | None = None
    email: str | None = None
    city: str | None = None


class Order(BaseModel):
    order_id: str
    customer_id: str
    order_date: datetime | None = None
    status: str
    total_brl: float = Field(ge=0)
    payment_method: str | None = None
    tracking_code: str | None = None
    estimated_delivery: datetime | None = None
    notes: str | None = None


class OrderItem(BaseModel):
    order_id: str
    product_id: str
    quantity: int = Field(gt=0)
