from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class DeliveryEstimate:
    cost: Decimal
    estimated_days: int


@runtime_checkable
class DeliveryProvider(Protocol):
    async def calculate_cost(
        self,
        *,
        address: dict[str, str],
        weight_kg: float,
        dimensions: dict[str, float],
    ) -> DeliveryEstimate: ...

    async def get_tracking_status(self, *, tracking_number: str) -> str: ...
