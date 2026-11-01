"""Modelos do catálogo: categoria, produto, promoção e produto com preço calculado."""

from datetime import datetime

from pydantic import BaseModel, Field

# Regra do manual (§3 e §6.2): 5% no PIX, exceto sobre preço já promocional.
PIX_DISCOUNT_PERCENT = 5.0

# Valores reais de `products.status`: active, discontinued, coming_soon.
# Só "active" pode ser oferecido ao cliente.
AVAILABLE_STATUS = "active"


class Category(BaseModel):
    category_id: str
    name: str
    description: str | None = None


class Product(BaseModel):
    product_id: str
    name: str
    price_brl: float = Field(gt=0)
    category_id: str
    description: str | None = None
    stock_quantity: int = Field(ge=0)
    status: str
    specs: str | None = None
    created_at: datetime | None = None

    @property
    def is_available(self) -> bool:
        """Pode ser oferecido: status ativo e com estoque (exclui descontinuado e "em breve")."""
        return self.status.strip().lower() == AVAILABLE_STATUS and self.stock_quantity > 0


class Promotion(BaseModel):
    promotion_id: str
    product_id: str
    discount_percent: float = Field(gt=0, le=100)
    description: str | None = None
    is_active: bool = False


class PricedProduct(BaseModel):
    """Produto + preços já calculados (é o que as tools devolvem ao LLM)."""

    product: Product
    list_price: float  # preço de tabela
    discount_percent: float  # 0 se não houver promoção ativa
    final_price: float  # preço com promoção
    pix_price: float | None  # None quando há promoção (não cumulativo)