from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import PaginationMeta as PaginationMeta

PayoutStatusLiteral = Literal["pending", "scheduled", "processing", "paid", "failed"]


class PayoutPayload(BaseModel):
    id: UUID
    brand_id: UUID
    brand_name: str
    sub_order_id: UUID
    amount: Decimal
    status: PayoutStatusLiteral
    payout_delay_days: int
    scheduled_at: datetime
    completed_at: datetime | None
    created_at: datetime


class PayoutMarkPaidRequest(BaseModel):
    status: Literal["paid"]


class PayoutResponse(BaseModel):
    data: PayoutPayload


class PayoutListResponse(BaseModel):
    data: list[PayoutPayload]
    meta: PaginationMeta
