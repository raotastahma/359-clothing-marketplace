from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CartItemCreateRequest(BaseModel):
    product_variant_id: UUID
    quantity: int = Field(ge=1)


class CartItemUpdateRequest(BaseModel):
    quantity: int = Field(ge=1)


class CartVariantPayload(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    product_slug: str
    vendor_code: str | None
    sku: str
    size: str
    color: str | None
    price_rub: Decimal
    compare_at_price_rub: Decimal | None
    stock_quantity: int
    brand_name: str
    image_url: str | None


class CartItemPayload(BaseModel):
    id: UUID
    product_variant: CartVariantPayload
    quantity: int


class CartPayload(BaseModel):
    items: list[CartItemPayload]
    total: Decimal
    items_count: int


class CartResponse(BaseModel):
    data: CartPayload
