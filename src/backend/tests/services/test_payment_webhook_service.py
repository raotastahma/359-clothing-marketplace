# Tests for PaymentWebhookService: signature verification, idempotency,
# sub-order/token creation, and fiscal receipt credential fallback behavior.
from __future__ import annotations

import hashlib
import hmac
import logging

# pyright: reportPrivateUsage=false
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.order_service import OrderService
from app.services.payment_webhook_service import (
    DatabaseSessionProtocol,
    InvalidWebhookSignatureError,
    PaymentWebhookService,
)


class _FakeResult:
    def mappings(self) -> _FakeResult:
        return self

    def first(self) -> Mapping[str, object] | None:
        return None

    def all(self) -> list[Mapping[str, object]]:
        return []


class _FakeDb:
    def __init__(self) -> None:
        self.execute_calls = 0
        self.commits = 0
        self.statements: list[str] = []
        self.execute_params: list[Mapping[str, object] | None] = []

    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _FakeResult:
        self.execute_calls += 1
        self.statements.append(str(statement))
        self.execute_params.append(params)
        return _FakeResult()

    async def commit(self) -> None:
        self.commits += 1


class _FakeNotificationService:
    def __init__(self, *, fail_order_paid: bool = False) -> None:
        self.calls: list[tuple[str, object]] = []
        self.fail_order_paid = fail_order_paid

    async def notify_order_paid(
        self,
        *,
        order: Mapping[str, object],
        items: list[Mapping[str, object]],
        brand_notification_emails: Mapping[object, list[str]],
        action_tokens: Mapping[object, object],
    ) -> None:
        if self.fail_order_paid:
            raise RuntimeError("notification enqueue failed")
        self.calls.append(
            (
                "notify_order_paid",
                {
                    "order": order,
                    "items": items,
                    "brand_notification_emails": brand_notification_emails,
                    "action_tokens": action_tokens,
                },
            )
        )

    async def notify_buyer_status_update(
        self,
        *,
        email: str,
        order_number: str,
        status: str,
        details: str,
        tracking_number: str | None = None,
    ) -> None:
        _ = email
        _ = order_number
        _ = status
        _ = details
        _ = tracking_number


class _FakeOrderService:
    def __init__(self, sub_orders: list[Mapping[str, object]]) -> None:
        self.sub_orders = sub_orders
        self.calls: list[tuple[str, object]] = []
        self.transitioned_at = datetime.now(UTC)

    async def transition_order(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("transition_order", kwargs))
        return {
            "id": kwargs["order_id"],
            "status": "paid",
            "tracking_number": None,
            "paid_at": self.transitioned_at,
            "shipped_at": None,
            "delivered_at": None,
        }

    async def create_sub_orders(self, **kwargs: object) -> list[Mapping[str, object]]:
        self.calls.append(("create_sub_orders", kwargs))
        return self.sub_orders

    async def get_order_payload_for_notifications(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("get_order_payload_for_notifications", kwargs))
        return {
            "id": kwargs["order_id"],
            "number": "ORD-TEST",
            "created_at": self.transitioned_at,
            "buyer_full_name": "Buyer",
            "buyer_phone": "+79001234567",
            "buyer_email": "buyer@example.com",
            "delivery_address": "Moscow, Tverskaya 1",
        }

    async def list_order_items(self, **kwargs: object) -> list[Mapping[str, object]]:
        self.calls.append(("list_order_items", kwargs))
        return [
            {
                "id": uuid4(),
                "order_id": kwargs["order_id"],
                "brand_id": self.sub_orders[0]["brand_id"],
                "product_variant_id": uuid4(),
                "quantity": 1,
                "unit_price": 1000,
                "commission_rate": 0.35,
                "commission_amount": 350,
                "vendor_code": "SKU-1",
                "size": "M",
                "color": None,
                "product_name": "Jacket",
            }
        ]

    async def get_brand_notification_emails(self, **kwargs: object) -> dict[object, list[str]]:
        self.calls.append(("get_brand_notification_emails", kwargs))
        return {
            self.sub_orders[0]["brand_id"]: ["brand@example.com"],
            self.sub_orders[1]["brand_id"]: ["brand2@example.com"],
        }


@pytest.mark.asyncio
async def test_verify_signature_hmac_success(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = PaymentWebhookService(db=cast(DatabaseSessionProtocol, db))
    raw_body = b'{"event":"payment.succeeded"}'

    old_secret = settings.yookassa_webhook_secret
    monkeypatch.setattr(settings, "yookassa_webhook_secret", "test-secret")
    expected = hmac.new(
        b"test-secret",
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    service._verify_signature(
        raw_body=raw_body,
        headers={"x-yookassa-signature": expected},
    )
    monkeypatch.setattr(settings, "yookassa_webhook_secret", old_secret)


@pytest.mark.asyncio
async def test_verify_signature_hmac_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = PaymentWebhookService(db=cast(DatabaseSessionProtocol, db))
    raw_body = b'{"event":"payment.succeeded"}'

    old_secret = settings.yookassa_webhook_secret
    monkeypatch.setattr(settings, "yookassa_webhook_secret", "test-secret")
    with pytest.raises(InvalidWebhookSignatureError):
        service._verify_signature(
            raw_body=raw_body,
            headers={"x-yookassa-signature": "wrong-signature"},
        )
    monkeypatch.setattr(settings, "yookassa_webhook_secret", old_secret)


@pytest.mark.asyncio
async def test_verify_signature_rejects_unconfigured_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb()
    service = PaymentWebhookService(db=cast(DatabaseSessionProtocol, db))

    monkeypatch.setattr(settings, "yookassa_webhook_secret", "")
    monkeypatch.setattr(settings, "yookassa_shop_id", "")
    monkeypatch.setattr(settings, "yookassa_secret_key", "")

    with pytest.raises(InvalidWebhookSignatureError):
        service._verify_signature(
            raw_body=b'{"event":"payment.succeeded"}',
            headers={},
        )


@pytest.mark.asyncio
async def test_create_receipt_returns_mock_url_without_credentials_outside_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb()
    service = PaymentWebhookService(db=cast(DatabaseSessionProtocol, db))
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "yookassa_shop_id", "")
    monkeypatch.setattr(settings, "yookassa_secret_key", "")

    receipt_url = await service._create_receipt(
        payment_row={"external_payment_id": "pay_123"},
        object_payload={},
        order_id=uuid4(),
    )

    assert receipt_url == "https://mock.yookassa.local/receipts/pay_123"


@pytest.mark.asyncio
async def test_create_receipt_fails_closed_without_credentials_in_production(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db = _FakeDb()
    service = PaymentWebhookService(db=cast(DatabaseSessionProtocol, db))
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "yookassa_shop_id", "")
    monkeypatch.setattr(settings, "yookassa_secret_key", "")

    with caplog.at_level(logging.WARNING, logger="app.services.payment_webhook_service"):
        receipt_url = await service._create_receipt(
            payment_row={"external_payment_id": "pay_123"},
            object_payload={},
            order_id=uuid4(),
        )

    # No fake receipt URL may leak into production data; a loud warning replaces it.
    assert receipt_url is None
    assert "skipping fiscal receipt" in caplog.text


@pytest.mark.asyncio
async def test_handle_payment_succeeded_is_idempotent() -> None:
    db = _FakeDb()
    service = PaymentWebhookService(db=cast(DatabaseSessionProtocol, db))

    await service._handle_payment_succeeded(
        payment_row={
            "id": uuid4(),
            "order_id": uuid4(),
            "external_payment_id": "pay_123",
            "status": "succeeded",
            "amount": 1000,
        },
        payload={"event": "payment.succeeded"},
        object_payload={"id": "pay_123"},
    )

    assert db.execute_calls == 0


@pytest.mark.asyncio
async def test_ensure_brand_action_tokens_uses_sub_order_ids() -> None:
    db = _FakeDb()
    service = PaymentWebhookService(db=cast(DatabaseSessionProtocol, db))

    order_id = uuid4()
    brand_a = uuid4()
    brand_b = uuid4()
    sub_order_a = uuid4()
    sub_order_b = uuid4()

    tokens = await service._ensure_brand_action_tokens(
        order_id=order_id,
        sub_orders=[
            {"id": sub_order_a, "brand_id": brand_a},
            {"id": sub_order_b, "brand_id": brand_b},
        ],
    )

    insert_params = [
        params
        for statement, params in zip(db.statements, db.execute_params, strict=False)
        if "INSERT INTO order_action_tokens" in statement
    ]
    assert set(tokens.keys()) == {brand_a, brand_b}
    assert len(insert_params) == 6
    assert {params["sub_order_id"] for params in insert_params if params is not None} == {
        sub_order_a,
        sub_order_b,
    }


@pytest.mark.asyncio
async def test_handle_payment_succeeded_creates_sub_orders_before_tokens() -> None:
    brand_a = uuid4()
    brand_b = uuid4()
    sub_order_a = uuid4()
    sub_order_b = uuid4()
    order_id = uuid4()
    order_service = _FakeOrderService(
        sub_orders=[
            {"id": sub_order_a, "brand_id": brand_a},
            {"id": sub_order_b, "brand_id": brand_b},
        ]
    )
    db = _FakeDb()
    service = PaymentWebhookService(db=cast(DatabaseSessionProtocol, db))
    service._order_service = cast(OrderService, order_service)
    service._notification_service = _FakeNotificationService()  # type: ignore[assignment]

    async def _fake_receipt(**kwargs: object) -> str | None:
        _ = kwargs
        return None

    service._create_receipt = _fake_receipt  # type: ignore[method-assign]

    await service._handle_payment_succeeded(
        payment_row={
            "id": uuid4(),
            "order_id": order_id,
            "external_payment_id": "pay_123",
            "status": "pending",
            "amount": 1000,
        },
        payload={"event": "payment.succeeded"},
        object_payload={"id": "pay_123"},
    )

    assert order_service.calls[0][0] == "transition_order"
    transition_kwargs = cast(dict[str, object], order_service.calls[0][1])
    assert transition_kwargs["commit"] is False
    assert order_service.calls[1][0] == "create_sub_orders"

    insert_params = [
        params
        for statement, params in zip(db.statements, db.execute_params, strict=False)
        if "INSERT INTO order_action_tokens" in statement
    ]
    assert len(insert_params) == 6
    assert {params["sub_order_id"] for params in insert_params if params is not None} == {
        sub_order_a,
        sub_order_b,
    }
    assert db.commits == 1


@pytest.mark.asyncio
async def test_handle_payment_succeeded_does_not_commit_when_paid_notification_fails() -> None:
    brand_a = uuid4()
    brand_b = uuid4()
    sub_order_a = uuid4()
    sub_order_b = uuid4()
    order_id = uuid4()
    order_service = _FakeOrderService(
        sub_orders=[
            {"id": sub_order_a, "brand_id": brand_a},
            {"id": sub_order_b, "brand_id": brand_b},
        ]
    )
    db = _FakeDb()
    service = PaymentWebhookService(db=cast(DatabaseSessionProtocol, db))
    service._order_service = cast(OrderService, order_service)
    service._notification_service = _FakeNotificationService(fail_order_paid=True)  # type: ignore[assignment]

    async def _fake_receipt(**kwargs: object) -> str | None:
        _ = kwargs
        return None

    service._create_receipt = _fake_receipt  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="notification enqueue failed"):
        await service._handle_payment_succeeded(
            payment_row={
                "id": uuid4(),
                "order_id": order_id,
                "external_payment_id": "pay_123",
                "status": "pending",
                "amount": 1000,
            },
            payload={"event": "payment.succeeded"},
            object_payload={"id": "pay_123"},
        )

    assert db.commits == 0


@pytest.mark.asyncio
async def test_handle_payment_succeeded_does_not_commit_when_sub_order_creation_fails() -> None:
    brand_a = uuid4()
    sub_order_a = uuid4()
    order_id = uuid4()
    order_service = _FakeOrderService(
        sub_orders=[
            {"id": sub_order_a, "brand_id": brand_a},
        ]
    )
    db = _FakeDb()
    service = PaymentWebhookService(db=cast(DatabaseSessionProtocol, db))
    service._order_service = cast(OrderService, order_service)
    service._notification_service = _FakeNotificationService()  # type: ignore[assignment]

    async def _fake_receipt(**kwargs: object) -> str | None:
        _ = kwargs
        return None

    async def _raise_create_sub_orders(**kwargs: object) -> list[Mapping[str, object]]:
        _ = kwargs
        raise RuntimeError("sub order creation failed")

    service._create_receipt = _fake_receipt  # type: ignore[method-assign]
    order_service.create_sub_orders = _raise_create_sub_orders  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        await service._handle_payment_succeeded(
            payment_row={
                "id": uuid4(),
                "order_id": order_id,
                "external_payment_id": "pay_123",
                "status": "pending",
                "amount": 1000,
            },
            payload={"event": "payment.succeeded"},
            object_payload={"id": "pay_123"},
        )

    assert db.commits == 0
    assert order_service.calls[0][0] == "transition_order"
    transition_kwargs = cast(dict[str, object], order_service.calls[0][1])
    assert transition_kwargs["commit"] is False
