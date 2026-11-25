from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
import asyncio
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from beartype import beartype
from yookassa import Configuration, Payment, Refund  # type: ignore[import-untyped]

from app.integrations.payments.protocol import (
    PaymentCreateResult,
    PaymentProvider,
)


class YooKassaProvider(PaymentProvider):
    @beartype
    def __init__(self, *, shop_id: str, secret_key: str) -> None:
        if not shop_id.strip() or not secret_key.strip():
            raise ValueError("YooKassa credentials are required.")
        self._shop_id = shop_id
        self._secret_key = secret_key

    @beartype
    def _configure(self) -> None:
        Configuration.account_id = self._shop_id
        Configuration.secret_key = self._secret_key

    @beartype
    async def create_payment(
        self,
        *,
        amount: Decimal,
        order_id: UUID,
        return_url: str,
        description: str,
    ) -> PaymentCreateResult:
        self._configure()
        payload = {
            "amount": {"value": str(amount.quantize(Decimal("0.01"))), "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": return_url},
            "capture": True,
            "description": description,
            "metadata": {"order_id": str(order_id)},
        }
        idempotence_key = str(uuid4())
        payment = await asyncio.to_thread(Payment.create, payload, idempotence_key)

        payment_id = str(getattr(payment, "id", ""))
        status = str(getattr(payment, "status", "pending"))
        confirmation = getattr(payment, "confirmation", None)
        payment_url = ""
        if confirmation is not None:
            payment_url = str(getattr(confirmation, "confirmation_url", ""))
        if not payment_url:
            raise RuntimeError("YooKassa response missing confirmation URL.")

        return PaymentCreateResult(
            external_payment_id=payment_id,
            payment_url=payment_url,
            status=status,
        )

    @beartype
    async def create_refund(
        self,
        *,
        payment_id: str,
        amount: Decimal,
        reason: str,
    ) -> str:
        self._configure()
        payload = {
            "payment_id": payment_id,
            "amount": {"value": str(amount.quantize(Decimal("0.01"))), "currency": "RUB"},
            "description": reason,
        }
        idempotence_key = str(uuid4())
        refund = await asyncio.to_thread(Refund.create, payload, idempotence_key)
        refund_id = cast(str, getattr(refund, "id", ""))
        if not refund_id:
            raise RuntimeError("YooKassa response missing refund id.")
        return refund_id
