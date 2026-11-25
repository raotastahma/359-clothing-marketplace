from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta as PaginationMeta

OrderStatusLiteral = Literal[
    "pending",
    "paid",
    "processing",
    "shipped",
    "delivered",
    "completed",
    "cancelled_by_buyer",
    "cancelled_by_brand",
    "returned",
]

DeliveryProviderLiteral = Literal["yandex_delivery"]


class OrderCreateRequest(BaseModel):
    address_id: UUID
    delivery_provider: DeliveryProviderLiteral = "yandex_delivery"
    delivery_method: str = Field(min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=500)


class OrderItemPayload(BaseModel):
    id: UUID
    product_variant_id: UUID
    brand_id: UUID
    product_name: str
    vendor_code: str | None
    size: str
    color: str | None
    quantity: int
    unit_price: Decimal
    commission_rate: Decimal
    commission_amount: Decimal


class SubOrderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    brand_name: str
    status: OrderStatusLiteral
    tracking_number: str | None
    items_count: int


class OrderDetailPayload(BaseModel):
    id: UUID
    status: OrderStatusLiteral
    total_amount: Decimal
    commission_total: Decimal
    customer_delivery_cost: Decimal
    delivery_provider: str | None
    delivery_method: str | None
    delivery_address: dict[str, object] | None
    items: list[OrderItemPayload]
    sub_orders: list[SubOrderSummary]
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime


class OrderSummaryPayload(BaseModel):
    id: UUID
    status: OrderStatusLiteral
    total_amount: Decimal
    customer_delivery_cost: Decimal
    items_count: int
    sub_orders: list[SubOrderSummary]
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime


class OrderCreatePayload(BaseModel):
    id: UUID
    status: OrderStatusLiteral
    total_amount: Decimal
    customer_delivery_cost: Decimal
    items: list[OrderItemPayload]
    payment_url: str


class OrderStatusPayload(BaseModel):
    id: UUID
    status: OrderStatusLiteral
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None


class OrderCreateResponse(BaseModel):
    data: OrderCreatePayload


class OrderDetailResponse(BaseModel):
    data: OrderDetailPayload


class OrderListResponse(BaseModel):
    data: list[OrderSummaryPayload]
    meta: PaginationMeta


class OrderStatusResponse(BaseModel):
    data: OrderStatusPayload
