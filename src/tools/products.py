"""Tools de catálogo: buscar_produto e consultar_disponibilidade."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.tools.common import brl, normalizar


# ---------- Entradas ----------

class BuscaProdutoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    termo: str | None = Field(
        None, max_length=100,
        description="Palavras do nome ou da descrição do produto (ex.: 'Takamine GD20', 'aço').",
    )
    categoria: str | None = Field(
        None, max_length=60,
        description="Nome da categoria, no plural (ex.: 'Violões', 'Guitarras').",
    )
    preco_min: float | None = Field(None, ge=0, description="Preço final mínimo em reais.")
    preco_max: float | None = Field(None, ge=0, description="Preço final máximo em reais.")
    somente_disponiveis: bool = Field(
        True, description="Se verdadeiro, só produtos ativos e com estoque.",
    )
    limite: int = Field(5, ge=1, le=10, description="Quantidade máxima de resultados.")

    @model_validator(mode="after")
    def _validar(self):
        if (self.preco_min is not None and self.preco_max is not None
                and self.preco_min > self.preco_max):
            raise ValueError("preco_min não pode ser maior que preco_max.")
        if not (self.termo or self.categoria
                or self.preco_min is not None or self.preco_max is not None):
            raise ValueError("Informe ao menos um filtro: termo, categoria ou faixa de preço.")
        return self


class DisponibilidadeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    product_id: str = Field(
        min_length=1, max_length=40,
        description="Código do produto, obtido em buscar_produto.",
    )


# ---------- Saídas ----------

class ProdutoInfo(BaseModel):
    product_id: str
    nome: str
    categoria_id: str
    descricao: str
    situacao: Literal["disponivel", "sem_estoque", "descontinuado", "em_breve"]
    preco_original: float
    desconto_percentual: float
    preco_final: float
    preco_pix: float | None  # None quando há promoção (Manual §6.2)
    preco_texto: str         # frase pronta para o cliente


class ProdutoDetalhe(ProdutoInfo):
    estoque: int
    especificacoes: str


class ResultadoBusca(BaseModel):
    produtos: list[ProdutoInfo]
    aviso: str | None = None


class ResultadoDisponibilidade(BaseModel):
    encontrado: bool
    produto: ProdutoDetalhe | None = None
    alternativas: list[ProdutoInfo] = []
    mensagem: str | None = None


# ---------- Helpers ----------

def _situacao(produto) -> str:
    if produto.status == "discontinued":
        return "descontinuado"
    if produto.status == "coming_soon":
        return "em_breve"
    return "disponivel" if produto.is_available else "sem_estoque"


def _texto_preco(priced) -> str:
    """Preço original + % + final em promoção (§6.2); PIX só sem promoção."""
    if priced.discount_percent > 0:
        return (f"de {brl(priced.list_price)} por {brl(priced.final_price)} "
                f"({priced.discount_percent:g}% de desconto; promoção não acumula com o desconto do PIX)")
    texto = brl(priced.final_price)
    if priced.pix_price is not None:
        texto += f" (ou {brl(priced.pix_price)} no PIX, 5% de desconto)"
    return texto


def _info(priced) -> ProdutoInfo:
    p = priced.product
    return ProdutoInfo(
        product_id=str(p.product_id), nome=p.name, categoria_id=str(p.category_id),
        descricao=p.description, situacao=_situacao(p),
        preco_original=priced.list_price, desconto_percentual=priced.discount_percent,
        preco_final=priced.final_price, preco_pix=priced.pix_price,
        preco_texto=_texto_preco(priced),
    )


def _resolver_categoria(products, texto: str) -> str | None:
    """Devolve o nome exato da categoria que casa com o texto, ou None."""
    alvo = normalizar(texto)
    for categoria in products.list_categories():
        nome = normalizar(categoria.name)
        if alvo in nome or nome in alvo:
            return categoria.name
    return None


# ---------- Tools ----------

def buscar_produto(repos, entrada: BuscaProdutoInput) -> ResultadoBusca:
    categoria = None
    if entrada.categoria:
        categoria = _resolver_categoria(repos.products, entrada.categoria)
        if categoria is None:
            nomes = ", ".join(c.name for c in repos.products.list_categories())
            return ResultadoBusca(
                produtos=[],
                aviso=(f"Categoria '{entrada.categoria}' não existe. "
                       f"Categorias válidas: {nomes}. Tente de novo com o nome exato."),
            )

    filtros = dict(query=entrada.termo or None, category=categoria,
                   min_price=entrada.preco_min, max_price=entrada.preco_max,
                   limit=entrada.limite)
    achados = repos.products.search(**filtros, only_available=entrada.somente_disponiveis)

    aviso = None
    if not achados and entrada.somente_disponiveis:
        # §7.3: se existe mas está indisponível, o cliente precisa saber disso.
        achados = repos.products.search(**filtros, only_available=False)
        if achados:
            aviso = ("Nenhum produto disponível para essa busca. Os itens abaixo correspondem, "
                     "mas estão indisponíveis: informe a situação e ofereça alternativas disponíveis.")
    if not achados:
        aviso = "Nenhum produto encontrado com esses filtros."
    return ResultadoBusca(produtos=[_info(p) for p in achados], aviso=aviso)


def consultar_disponibilidade(repos, entrada: DisponibilidadeInput) -> ResultadoDisponibilidade:
    pid = entrada.product_id
    priced = repos.products.get_priced(pid) or repos.products.get_priced(pid.upper())
    if priced is None:
        return ResultadoDisponibilidade(
            encontrado=False,
            mensagem="Produto não encontrado. Use buscar_produto para localizar o código correto.",
        )
    detalhe = ProdutoDetalhe(
        **_info(priced).model_dump(),
        estoque=priced.product.stock_quantity,
        especificacoes=priced.product.specs,
    )
    alternativas = []
    if detalhe.situacao != "disponivel":
        alternativas = [_info(a) for a in repos.products.suggest_alternatives(priced.product.product_id)]
    return ResultadoDisponibilidade(encontrado=True, produto=detalhe, alternativas=alternativas)