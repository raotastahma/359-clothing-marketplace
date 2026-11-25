from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.order import OrderStatusLiteral, PaginationMeta

SlaStatusLiteral = Literal["on_time", "at_risk", "overdue"]


class BrandPortalOrderItemPayload(BaseModel):
    product_name: str
    size: str
    quantity: int
    unit_price: Decimal
    image_url: str | None


class BrandPortalOrderPayload(BaseModel):
    id: UUID
    parent_order_id: UUID
    status: OrderStatusLiteral
    items: list[BrandPortalOrderItemPayload]
    items_total: Decimal
    commission_total: Decimal
    payout_amount: Decimal
    confirmation_deadline: datetime | None
    shipping_deadline: datetime | None
    sla_status: SlaStatusLiteral
    created_at: datetime


class BrandPortalOrderDetailPayload(BrandPortalOrderPayload):
    delivery_address: dict[str, object] | None
    tracking_number: str | None
    confirmed_at: datetime | None
    shipped_at: datetime | None


class BrandPortalOrderActionPayload(BaseModel):
    id: UUID
    status: OrderStatusLiteral
    confirmation_deadline: datetime | None
    shipping_deadline: datetime | None
    sla_status: SlaStatusLiteral
    confirmed_at: datetime | None = None
    tracking_number: str | None = None
    shipped_at: datetime | None = None


class BrandPortalOrderShipRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    tracking_number: str = Field(min_length=1, max_length=100)


class BrandPortalOrderListResponse(BaseModel):
    data: list[BrandPortalOrderPayload]
    meta: PaginationMeta


class BrandPortalOrderDetailResponse(BaseModel):
    data: BrandPortalOrderDetailPayload


class BrandPortalOrderActionResponse(BaseModel):
    data: BrandPortalOrderActionPayload
