from __future__ import annotations

import enum
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

UTC_NOW_SQL: Final[str] = "now()"


class GenderType(str, enum.Enum):
    MEN = "men"
    WOMEN = "women"
    UNISEX = "unisex"


class ProductStatus(str, enum.Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    ARCHIVED = "archived"


class FeedSyncStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class OrderActionType(str, enum.Enum):
    CONFIRM = "confirm"
    CANCEL = "cancel"
    SHIP = "ship"


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        server_default=text("0.3500"),
    )
    notification_emails: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    yml_feed_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    yml_sync_schedule: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        server_default=text("'0 */4 * * *'"),
    )
    payout_bank_details: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text(UTC_NOW_SQL),
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    gender: Mapped[GenderType] = mapped_column(
        PgEnum(GenderType, name="gender_type", create_type=False),
        nullable=False,
        server_default=text("'unisex'::gender_type"),
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    brand_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fabric_composition: Mapped[str | None] = mapped_column(Text, nullable=True)
    care_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    season: Mapped[str | None] = mapped_column(String(50), nullable=True)
    base_price_rub: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sale_price_rub: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    product_status: Mapped[ProductStatus] = mapped_column(
        PgEnum(ProductStatus, name="product_status", create_type=False),
        nullable=False,
        server_default=text("'active'::product_status"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    is_new_arrival: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text(UTC_NOW_SQL),
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text(UTC_NOW_SQL),
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    product_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    size: Mapped[str] = mapped_column(String(20), nullable=False)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    vendor_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price_rub: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    compare_at_price_rub: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    product_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)


class FeedSyncLog(Base):
    __tablename__ = "feed_sync_logs"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    brand_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text(UTC_NOW_SQL),
    )
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[FeedSyncStatus] = mapped_column(
        PgEnum(FeedSyncStatus, name="feed_sync_status", create_type=False),
        nullable=False,
        server_default=text("'running'::feed_sync_status"),
    )
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    unmatched_codes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text(UTC_NOW_SQL),
    )


class OrderActionToken(Base):
    __tablename__ = "order_action_tokens"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    sub_order_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("sub_orders.id", ondelete="CASCADE"),
        nullable=True,
    )
    order_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    brand_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_type: Mapped[OrderActionType] = mapped_column(
        PgEnum(OrderActionType, name="order_action_type", create_type=False),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text(UTC_NOW_SQL),
    )
