from __future__ import annotations

import pytest

from app.integrations.delivery.yandex_delivery_provider import YandexDeliveryProvider


@pytest.mark.asyncio
async def test_fallback_calculate_cost_without_credentials() -> None:
    provider = YandexDeliveryProvider(api_key="", client_id="", base_url="https://api.example.com")

    estimate = await provider.calculate_cost(
        address={"city": "Moscow", "street": "Tverskaya 1", "postal_code": "125009"},
        weight_kg=1.5,
        dimensions={"length_cm": 30.0, "width_cm": 20.0, "height_cm": 10.0},
    )

    assert estimate.cost > 0
    assert estimate.estimated_days >= 1


@pytest.mark.asyncio
async def test_fallback_tracking_without_credentials() -> None:
    provider = YandexDeliveryProvider(api_key="", client_id="", base_url="https://api.example.com")

    tracking_status = await provider.get_tracking_status(tracking_number="YD-TEST123")

    assert tracking_status == "shipped"
