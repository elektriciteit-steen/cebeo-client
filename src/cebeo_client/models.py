"""Data models for Cebeo API responses."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class Article:
    """Represents an article from the Cebeo catalog.

    Fields map to the cebeoXML response structure.
    """

    supplier_item_id: str
    customer_item_id: str | None
    brand_code: str
    brand_name: str
    reference: str
    description: str
    stock: int
    stock_code: str  # 'A' = available, others indicate limited/no stock
    unit_of_measure: str  # MTR, PCE, etc.
    net_price: Decimal
    tarif_price: Decimal
    ecotax: Decimal
    recupel: Decimal
    sabam: Decimal
    vat_rate: Decimal
    sales_pack_quantity: int
    reel_code: str | None = None
    reel_length: int | None = None
    promotion_code: str | None = None

    @property
    def is_available(self) -> bool:
        """Check if article is available in stock."""
        return self.stock_code == "A" and self.stock > 0


@dataclass
class ArticleSearchResult:
    """Result of an article search operation."""

    articles: list[Article]
    total_count: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        """Check if there are more results available."""
        return self.offset + len(self.articles) < self.total_count


@dataclass
class OrderLine:
    """Represents an order line from a Cebeo order.

    Fields map to the cebeoXML OrderLine response structure.
    """

    supplier_order_line_id: str
    supplier_item_id: str
    description: str
    unit_of_measure: str  # PCE, MTR
    ordered_quantity: int
    net_price: Decimal
    stock: int
    stock_code: str
    customer_order_line_id: str | None = None
    customer_item_id: str | None = None
    ean: str | None = None  # EAN/barcode
    brand_code: str | None = None
    brand_name: str | None = None
    reference: str | None = None
    reel_code: str | None = None
    reel_length: int | None = None
    backorder_quantity: int | None = None
    backorder_delivery_date: date | None = None
    delivery_quantity: int | None = None
    delivery_date: date | None = None
    requested_delivery_date: date | None = None


@dataclass
class Order:
    """Represents a Cebeo order.

    Fields map to the cebeoXML Order response structure.
    """

    supplier_order_id: str
    customer_order_id: str
    order_date: date
    lines: list[OrderLine]
    customer_order_ref: str | None = None
    ordered_by: str | None = None
    delivery_address: dict | None = None
    comments: list[str] | None = None
