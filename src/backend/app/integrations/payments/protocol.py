from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PaymentCreateResult:
    external_payment_id: str
    payment_url: str
    status: str


@runtime_checkable
class PaymentProvider(Protocol):
    async def create_payment(
        self,
        *,
        amount: Decimal,
        order_id: UUID,
        return_url: str,
        description: str,
    ) -> PaymentCreateResult: ...

    async def create_refund(
        self,
        *,
        payment_id: str,
        amount: Decimal,
        reason: str,
    ) -> str: ...
