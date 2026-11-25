from __future__ import annotations

from pydantic import BaseModel


class PaymentWebhookAckPayload(BaseModel):
    status: str


class PaymentWebhookAckResponse(BaseModel):
    data: PaymentWebhookAckPayload
