from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BrandPortalFinancePeriod(BaseModel):
    date_from: date = Field(alias="from", serialization_alias="from")
    date_to: date = Field(alias="to", serialization_alias="to")

    model_config = {"populate_by_name": True}


class BrandPortalAnalyticsSummaryPayload(BaseModel):
    period: BrandPortalFinancePeriod
    orders_count: int
    total_sales: Decimal
    commission_rate: Decimal
    commission_total: Decimal
    payout_pending: Decimal
    payout_completed: Decimal


class BrandPortalAnalyticsSummaryResponse(BaseModel):
    data: BrandPortalAnalyticsSummaryPayload


class BrandPortalTopProductPayload(BaseModel):
    product_id: UUID
    product_name: str
    units_sold: int
    total_sales: Decimal


class BrandPortalTopProductsResponse(BaseModel):
    data: list[BrandPortalTopProductPayload]


BrandPortalPayoutStatusLiteral = Literal[
    "pending",
    "scheduled",
    "processing",
    "completed",
    "paid",
    "failed",
]


class BrandPortalPayoutPayload(BaseModel):
    id: UUID
    sub_order_id: UUID
    amount: Decimal
    commission_rate: Decimal
    status: BrandPortalPayoutStatusLiteral
    scheduled_at: datetime
    completed_at: datetime | None
    created_at: datetime


class BrandPortalPaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int


class BrandPortalPayoutListResponse(BaseModel):
    data: list[BrandPortalPayoutPayload]
    meta: BrandPortalPaginationMeta
