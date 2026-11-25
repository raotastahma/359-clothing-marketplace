from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class DeliveryCalculateResponseData(BaseModel):
    cost: Decimal
    estimated_days: int = Field(ge=1)


class DeliveryCalculateResponse(BaseModel):
    data: DeliveryCalculateResponseData
