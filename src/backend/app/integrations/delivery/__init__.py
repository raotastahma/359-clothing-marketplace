from __future__ import annotations

from beartype import beartype

from app.core.config import settings
from app.integrations.delivery.protocol import DeliveryProvider
from app.integrations.delivery.yandex_delivery_provider import YandexDeliveryProvider


@beartype
def get_delivery_provider() -> DeliveryProvider:
    return YandexDeliveryProvider(
        api_key=settings.yandex_delivery_api_key,
        client_id=settings.yandex_delivery_client_id,
        base_url=settings.yandex_delivery_base_url,
    )
