from __future__ import annotations

from decimal import Decimal

import httpx
from beartype import beartype

from app.integrations.delivery.protocol import DeliveryEstimate, DeliveryProvider


class YandexDeliveryProvider(DeliveryProvider):
    @beartype
    def __init__(self, *, api_key: str, client_id: str, base_url: str) -> None:
        self._api_key = api_key
        self._client_id = client_id
        self._base_url = base_url.rstrip("/")

    @beartype
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "X-Client-ID": self._client_id,
            "Content-Type": "application/json",
        }

    @beartype
    async def calculate_cost(
        self,
        *,
        address: dict[str, str],
        weight_kg: float,
        dimensions: dict[str, float],
    ) -> DeliveryEstimate:
        # Fallback MVP estimate when credentials are absent.
        if not self._api_key or not self._client_id:
            base = Decimal("300.00")
            weight_component = Decimal(str(max(weight_kg, 0.1))) * Decimal("100.00")
            return DeliveryEstimate(
                cost=(base + weight_component).quantize(Decimal("0.01")), estimated_days=3
            )

        payload = {
            "destination": address,
            "weight_kg": weight_kg,
            "dimensions": dimensions,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self._base_url}/pricing/calculate",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        cost_raw = data.get("cost", 0)
        days_raw = data.get("estimated_days", 3)
        return DeliveryEstimate(cost=Decimal(str(cost_raw)), estimated_days=max(int(days_raw), 1))

    @beartype
    async def get_tracking_status(self, *, tracking_number: str) -> str:
        if not self._api_key or not self._client_id:
            # Deterministic stub for local/dev mode.
            return "shipped"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._base_url}/shipments/{tracking_number}/status",
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
        return str(data.get("status", "unknown"))
