"""Sample dataclass definitions for testing DataclassFieldsExtractor."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar


@dataclass
class User:
    """A user dataclass."""

    name: str
    email: str
    age: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    bio: str | None = None


@dataclass
class Config:
    """Application configuration."""

    debug: bool = False
    port: int = 8080
    host: str = "localhost"
    database_url: str | None = None
    max_connections: int = field(default=100)
    allowed_origins: list = field(default_factory=lambda: ["*"])


@dataclass
class Point:
    """A 2D point."""

    x: float
    y: float


@dataclass
class InventoryItem:
    """An item in an inventory."""

    name: str
    quantity: int = 0
    price: float = 0.0
    # ClassVar is NOT a field
    total_items: ClassVar[int] = 0


@dataclass
class Order:
    """An order with various field types."""

    order_id: str
    items: list[str] = field(default_factory=list)
    total: float = 0.0
    shipping_address: str | None = None
    status: str = "pending"
    tags: set[str] = field(default_factory=set)
    metadata: dict = field(default_factory=dict)


@dataclass
class Response:
    """HTTP response template."""

    status_code: int = 200
    message: str = "OK"
    data: dict | None = None


@dataclass
class Container:
    """Container with InitVar field (should be skipped)."""

    from dataclasses import InitVar

    name: str
    data: list = field(default_factory=list)
    size: InitVar[int] = 0
