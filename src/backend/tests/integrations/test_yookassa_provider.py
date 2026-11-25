from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

import app.integrations.payments.yookassa_provider as yookassa_module
from app.core.config import settings
from app.integrations.payments import get_payment_provider
from app.integrations.payments.local import LocalPaymentProvider
from app.integrations.payments.yookassa_provider import YooKassaProvider


class _FakeConfirmation:
    def __init__(self, confirmation_url: str) -> None:
        self.confirmation_url = confirmation_url


class _FakePaymentResponse:
    def __init__(self, *, payment_id: str, status: str, confirmation_url: str) -> None:
        self.id = payment_id
        self.status = status
        self.confirmation = _FakeConfirmation(confirmation_url)


class _FakePaymentAPI:
    @staticmethod
    def create(payload: dict[str, object], idempotence_key: str) -> _FakePaymentResponse:
        _ = payload
        _ = idempotence_key
        return _FakePaymentResponse(
            payment_id="pay_123",
            status="pending",
            confirmation_url="https://pay.example/checkout",
        )


class _FakeRefundResponse:
    def __init__(self, refund_id: str) -> None:
        self.id = refund_id


class _FakeRefundAPI:
    @staticmethod
    def create(payload: dict[str, object], idempotence_key: str) -> _FakeRefundResponse:
        _ = payload
        _ = idempotence_key
        return _FakeRefundResponse("refund_999")


def test_get_payment_provider_uses_local_provider_without_dev_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "yookassa_shop_id", "")
    monkeypatch.setattr(settings, "yookassa_secret_key", "")

    assert isinstance(get_payment_provider(), LocalPaymentProvider)


def test_get_payment_provider_requires_production_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "yookassa_shop_id", "")
    monkeypatch.setattr(settings, "yookassa_secret_key", "")

    with pytest.raises(ValueError):
        get_payment_provider()


@pytest.mark.asyncio
async def test_yookassa_provider_create_payment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yookassa_module, "Payment", _FakePaymentAPI)
    monkeypatch.setattr(yookassa_module, "Refund", _FakeRefundAPI)

    provider = YooKassaProvider(shop_id="shop-id", secret_key="secret-key")
    result = await provider.create_payment(
        amount=Decimal("15000.00"),
        order_id=uuid4(),
        return_url="https://app.example/orders/success",
        description="Order #1",
    )

    assert result.external_payment_id == "pay_123"
    assert result.status == "pending"
    assert result.payment_url == "https://pay.example/checkout"


@pytest.mark.asyncio
async def test_yookassa_provider_refund(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yookassa_module, "Payment", _FakePaymentAPI)
    monkeypatch.setattr(yookassa_module, "Refund", _FakeRefundAPI)

    provider = YooKassaProvider(shop_id="shop-id", secret_key="secret-key")
    refund_id = await provider.create_refund(
        payment_id="pay_123",
        amount=Decimal("15000.00"),
        reason="Customer cancellation",
    )

    assert refund_id == "refund_999"
