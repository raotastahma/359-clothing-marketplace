from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.payout import PayoutPayload


class BrandSummary(BaseModel):
    brand_id: UUID
    brand_name: str
    sales: Decimal
    commission: Decimal
    payouts_completed: Decimal
    payouts_pending: Decimal


class FinancePeriod(BaseModel):
    date_from: date = Field(alias="from", serialization_alias="from")
    date_to: date = Field(alias="to", serialization_alias="to")

    model_config = {"populate_by_name": True}


class FinanceReportPayload(BaseModel):
    period: FinancePeriod
    total_sales: Decimal
    total_commission: Decimal
    total_payouts_completed: Decimal
    total_payouts_pending: Decimal
    total_refunds: Decimal
    brands_summary: list[BrandSummary]


class FinanceReportResponse(BaseModel):
    data: FinanceReportPayload


class BrandBalancePayload(BaseModel):
    brand_id: UUID
    brand_name: str
    commission_rate: Decimal
    total_earned: Decimal
    total_paid: Decimal
    pending_payout: Decimal
    recent_payouts: list[PayoutPayload]


class BrandBalanceResponse(BaseModel):
    data: BrandBalancePayload
