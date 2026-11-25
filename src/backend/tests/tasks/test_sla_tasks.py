from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest

from app.tasks.celery_app import celery_app
from app.tasks.sla_tasks import DatabaseSessionProtocol, check_sla_deadlines


class _FakeResult:
    def __init__(self, rows: list[Mapping[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeResult:
        return self

    def all(self) -> list[Mapping[str, object]]:
        return list(self._rows)


class _FakeDb:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self._responses: list[_FakeResult] = []

    def push_response(self, rows: list[Mapping[str, object]]) -> None:
        self._responses.append(_FakeResult(rows))

    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _FakeResult:
        _ = params
        self.statements.append(str(statement))
        if self._responses:
            return self._responses.pop(0)
        return _FakeResult([])


class _FakeNotificationService:
    def __init__(self) -> None:
        self.alerts: list[dict[str, object]] = []

    async def send_sla_alert(
        self,
        *,
        to: str,
        sub_order: Mapping[str, object],
        alert_type: str,
    ) -> None:
        self.alerts.append(
            {
                "to": to,
                "sub_order_id": sub_order["id"],
                "alert_type": alert_type,
            }
        )


def _sub_order_row(*, status: str) -> dict[str, object]:
    return {
        "id": uuid4(),
        "order_id": uuid4(),
        "brand_id": uuid4(),
        "brand_name": "MASLOV",
        "status": status,
        "confirmation_deadline": datetime(2026, 2, 1, tzinfo=UTC),
        "shipping_deadline": datetime(2026, 2, 2, tzinfo=UTC),
    }


@pytest.mark.asyncio
async def test_check_sla_deadlines_alerts_for_overdue_sub_orders() -> None:
    db = _FakeDb()
    notification_service = _FakeNotificationService()
    confirmation_row = _sub_order_row(status="paid")
    shipping_row = _sub_order_row(status="processing")
    db.push_response([confirmation_row])
    db.push_response([shipping_row])

    sent_count = await check_sla_deadlines(
        db=cast(DatabaseSessionProtocol, db),
        notification_service=notification_service,
        head_of_partnerships_email="head@example.com",
    )

    assert sent_count == 2
    assert notification_service.alerts == [
        {
            "to": "head@example.com",
            "sub_order_id": confirmation_row["id"],
            "alert_type": "confirmation_overdue",
        },
        {
            "to": "head@example.com",
            "sub_order_id": shipping_row["id"],
            "alert_type": "shipping_overdue",
        },
    ]
    assert "WHERE so.status = 'paid'" in db.statements[0]
    assert "WHERE so.status = 'processing'" in db.statements[1]


@pytest.mark.asyncio
async def test_check_sla_deadlines_skips_when_alert_email_missing() -> None:
    db = _FakeDb()
    notification_service = _FakeNotificationService()

    sent_count = await check_sla_deadlines(
        db=cast(DatabaseSessionProtocol, db),
        notification_service=notification_service,
        head_of_partnerships_email="",
    )

    assert sent_count == 0
    assert notification_service.alerts == []
    assert db.statements == []


def test_check_sla_deadlines_registered_hourly() -> None:
    celery_conf = cast(Any, celery_app.conf)  # pyright: ignore[reportUnknownMemberType]
    beat_schedule = cast(Mapping[str, Mapping[str, object]], celery_conf.beat_schedule)
    schedule = beat_schedule["sla-check-deadlines"]

    assert schedule["task"] == "sla.check_deadlines"
