from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import order_actions
from app.main import app
from app.services.order_action_service import OrderActionResult


def test_ship_action_link_opens_html_form() -> None:
    token = "00000000-0000-0000-0000-000000000001"

    with TestClient(app) as client:
        response = client.get(f"/api/v1/orders/actions/{token}/ship")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "method='post'" in response.text
    assert "name='tracking_number'" in response.text


def test_ship_action_accepts_json_body(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "00000000-0000-0000-0000-000000000001"
    captured: dict[str, str] = {}

    async def _skip_rate_limit(**kwargs: object) -> None:
        _ = kwargs

    class _FakeOrderActionService:
        def __init__(self, *, db: object) -> None:
            _ = db

        async def ship(self, *, token: str, tracking_number: str) -> OrderActionResult:
            captured["token"] = token
            captured["tracking_number"] = tracking_number
            return OrderActionResult(
                order_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                status="shipped",
                title="Заказ отправлен",
                message="Статус заказа обновлён, трек-номер сохранён.",
            )

    monkeypatch.setattr(order_actions, "_enforce_rate_limit", _skip_rate_limit)
    monkeypatch.setattr(order_actions, "OrderActionService", _FakeOrderActionService)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/orders/actions/{token}/ship",
            json={"tracking_number": " YD-123456789 "},
        )

    assert response.status_code == 200
    assert captured == {"token": token, "tracking_number": "YD-123456789"}


def test_ship_action_accepts_tracking_number_form_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "00000000-0000-0000-0000-000000000001"
    captured: dict[str, str] = {}

    async def _skip_rate_limit(**kwargs: object) -> None:
        _ = kwargs

    class _FakeOrderActionService:
        def __init__(self, *, db: object) -> None:
            _ = db

        async def ship(self, *, token: str, tracking_number: str) -> OrderActionResult:
            captured["token"] = token
            captured["tracking_number"] = tracking_number
            return OrderActionResult(
                order_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                status="shipped",
                title="Заказ отправлен",
                message="Статус заказа обновлён, трек-номер сохранён.",
            )

    monkeypatch.setattr(order_actions, "_enforce_rate_limit", _skip_rate_limit)
    monkeypatch.setattr(order_actions, "OrderActionService", _FakeOrderActionService)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/orders/actions/{token}/ship",
            data={"tracking_number": " YD-123456789 "},
        )

    assert response.status_code == 200
    assert captured == {"token": token, "tracking_number": "YD-123456789"}
