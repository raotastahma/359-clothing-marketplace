from __future__ import annotations

from beartype import beartype

from app.core.config import settings
from app.integrations.payments.local import LocalPaymentProvider
from app.integrations.payments.protocol import PaymentProvider
from app.integrations.payments.yookassa_provider import YooKassaProvider


@beartype
def get_payment_provider() -> PaymentProvider:
    if (
        not settings.yookassa_shop_id.strip() or not settings.yookassa_secret_key.strip()
    ) and settings.app_env.strip().lower() != "production":
        return LocalPaymentProvider()

    return YooKassaProvider(
        shop_id=settings.yookassa_shop_id,
        secret_key=settings.yookassa_secret_key,
    )
