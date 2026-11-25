from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

import app.services.notification_service as notification_module
from app.services.notification_service import ActionTokens, NotificationService


def test_group_items_by_brand_splits_items() -> None:
    service = NotificationService(api_base_url="https://api.example.com/api/v1")
    brand_a = uuid4()
    brand_b = uuid4()
    grouped = service.group_items_by_brand(
        [
            {"brand_id": str(brand_a), "vendor_code": "A-1"},
            {"brand_id": str(brand_a), "vendor_code": "A-2"},
            {"brand_id": str(brand_b), "vendor_code": "B-1"},
        ]
    )

    assert len(grouped[brand_a]) == 2
    assert len(grouped[brand_b]) == 1


@pytest.mark.asyncio
async def test_notify_order_paid_enqueues_brand_and_buyer_emails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = NotificationService(api_base_url="https://api.example.com/api/v1")
    brand_id = uuid4()
    calls: list[tuple[str, dict[str, object]]] = []

    def _brand_delay(**kwargs: object) -> None:
        calls.append(("brand", dict(kwargs)))

    def _buyer_delay(**kwargs: object) -> None:
        calls.append(("buyer", dict(kwargs)))

    monkeypatch.setattr(notification_module.send_brand_new_order_email_task, "delay", _brand_delay)
    monkeypatch.setattr(notification_module.send_buyer_status_email_task, "delay", _buyer_delay)

    await service.notify_order_paid(
        order={
            "id": str(uuid4()),
            "number": "359-001",
            "created_at": datetime(2026, 2, 23, 12, 0, 0),
            "buyer_full_name": "Ivan Petrov",
            "buyer_phone": "+79001234567",
            "delivery_address": "Moscow",
            "buyer_email": "buyer@example.com",
        },
        items=[{"brand_id": str(brand_id), "vendor_code": "SKU-1", "quantity": 1}],
        brand_notification_emails={brand_id: ["orders@brand.ru"]},
        action_tokens={brand_id: ActionTokens(confirm="c-token", cancel="x-token", ship="s-token")},
    )

    assert len(calls) == 2
    brand_call = calls[0]
    buyer_call = calls[1]
    assert brand_call[0] == "brand"
    assert "actions" in brand_call[1]
    assert brand_call[1]["actions"] == {
        "confirm": "https://api.example.com/api/v1/orders/actions/c-token/confirm",
        "cancel": "https://api.example.com/api/v1/orders/actions/x-token/cancel",
        "ship": "https://api.example.com/api/v1/orders/actions/s-token/ship",
    }
    assert brand_call[1]["to"] == "orders@brand.ru"
    assert buyer_call[0] == "buyer"
    assert buyer_call[1]["template_id"] == "buyer_order_confirmed"


@pytest.mark.asyncio
async def test_send_sla_alert_enqueues_internal_email(monkeypatch: pytest.MonkeyPatch) -> None:
    service = NotificationService(api_base_url="https://api.example.com/api/v1")
    sub_order_id = uuid4()
    calls: list[dict[str, object]] = []

    def _delay(**kwargs: object) -> None:
        calls.append(dict(kwargs))

    monkeypatch.setattr(notification_module.send_transactional_email_task, "delay", _delay)

    await service.send_sla_alert(
        to="partners@example.com",
        sub_order={
            "id": sub_order_id,
            "order_id": uuid4(),
            "brand_id": uuid4(),
            "brand_name": "MASLOV",
            "status": "paid",
            "confirmation_deadline": datetime(2026, 2, 23, 12, 0, 0),
            "shipping_deadline": None,
        },
        alert_type="confirmation_overdue",
    )

    assert len(calls) == 1
    assert calls[0]["to"] == "partners@example.com"
    assert calls[0]["template_id"] == "sla_alert_to_head_of_partnerships"
    context = calls[0]["context"]
    assert isinstance(context, dict)
    assert context["alert_type"] == "confirmation_overdue"
    assert context["sub_order_id"] == str(sub_order_id)
    assert context["brand_name"] == "MASLOV"
    assert context["status"] == "paid"
    assert context["confirmation_deadline"] == "2026-02-23 12:00:00"
    assert context["shipping_deadline"] == ""
