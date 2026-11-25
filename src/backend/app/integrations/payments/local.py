from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from beartype import beartype

from app.integrations.payments.protocol import PaymentCreateResult


class LocalPaymentProvider:
    @beartype
    async def create_payment(
        self,
        *,
        amount: Decimal,
        order_id: UUID,
        return_url: str,
        description: str,
    ) -> PaymentCreateResult:
        _ = amount
        _ = return_url
        _ = description
        return PaymentCreateResult(
            external_payment_id=f"local-{order_id}",
            payment_url="",
            status="pending",
        )

    @beartype
    async def create_refund(
        self,
        *,
        payment_id: str,
        amount: Decimal,
        reason: str,
    ) -> str:
        _ = amount
        _ = reason
        return f"local-refund-{payment_id}"
