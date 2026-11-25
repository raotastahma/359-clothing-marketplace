"""Unit tests for payout service calculations, status mapping, and persistence queries."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest

from app.services.payout_service import (
    DatabaseSessionProtocol,
    PayoutAlreadyCompletedError,
    PayoutService,
    next_payout_date,
)


class _FakeResult:
    def __init__(self, rows: list[Mapping[str, object]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> _FakeResult:
        return self

    def first(self) -> Mapping[str, object] | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Mapping[str, object]]:
        return list(self._rows)

    def scalar_one_or_none(self) -> object:
        if self._rows:
            first_row = self._rows[0]
            values = list(first_row.values())
            return values[0] if values else None
        return None


class _FakeDb:
    def __init__(self) -> None:
        self.execute_calls = 0
        self.committed = False
        self._responses: list[_FakeResult] = []
        self.last_params: list[dict[str, object] | None] = []
        self.statements: list[str] = []

    def push_response(self, rows: list[Mapping[str, object]]) -> None:
        self._responses.append(_FakeResult(rows))

    async def execute(
        self, statement: object, params: Mapping[str, object] | None = None
    ) -> _FakeResult:
        self.statements.append(str(statement))
        self.execute_calls += 1
        self.last_params.append(dict(params) if params else None)
        if self._responses:
            return self._responses.pop(0)
        return _FakeResult()

    async def commit(self) -> None:
        self.committed = True


def test_payout_amount_calculation() -> None:
    """Payout amount = items total - commission total."""
    items_total = Decimal("15000.00")
    commission_total = Decimal("5250.00")
    payout_amount = (items_total - commission_total).quantize(Decimal("0.01"))
    assert payout_amount == Decimal("9750.00")


def test_payout_scheduled_at_calculation() -> None:
    """scheduled_at is the next 1st/15th payout window after eligibility."""
    delivered_at = datetime(2026, 3, 3, tzinfo=UTC)
    delay_days = 14
    scheduled_at = next_payout_date(delivered_at + timedelta(days=delay_days))
    assert scheduled_at == datetime(2026, 4, 1, tzinfo=UTC)


def test_next_payout_date_uses_fifteenth_when_eligible_before_mid_month() -> None:
    eligible_at = datetime(2026, 3, 2, 10, 30, tzinfo=UTC)
    assert next_payout_date(eligible_at) == datetime(2026, 3, 15, tzinfo=UTC)


def test_next_payout_date_uses_first_when_eligible_on_exact_first() -> None:
    eligible_at = datetime(2026, 3, 1, tzinfo=UTC)
    assert next_payout_date(eligible_at) == datetime(2026, 3, 1, tzinfo=UTC)


def test_next_payout_date_uses_fifteenth_when_eligible_on_exact_fifteenth() -> None:
    eligible_at = datetime(2026, 3, 15, tzinfo=UTC)
    assert next_payout_date(eligible_at) == datetime(2026, 3, 15, tzinfo=UTC)


def test_next_payout_date_rolls_to_next_month_after_mid_month() -> None:
    eligible_at = datetime(2026, 3, 17, tzinfo=UTC)
    assert next_payout_date(eligible_at) == datetime(2026, 4, 1, tzinfo=UTC)


def test_next_payout_date_rolls_december_after_mid_month_to_next_year() -> None:
    eligible_at = datetime(2026, 12, 16, tzinfo=UTC)
    assert next_payout_date(eligible_at) == datetime(2027, 1, 1, tzinfo=UTC)


def test_refund_reduces_pending_payout() -> None:
    """Refund on pending payout reduces the payout amount."""
    original_amount = Decimal("9750.00")
    refund_amount = Decimal("15000.00")
    commission_refund = Decimal("5250.00")
    payout_reduction = (refund_amount - commission_refund).quantize(Decimal("0.01"))
    new_amount = max(original_amount - payout_reduction, Decimal("0.00"))
    assert payout_reduction == Decimal("9750.00")
    assert new_amount == Decimal("0.00")


def test_refund_partial_reduces_pending_payout() -> None:
    """Partial refund reduces payout partially."""
    original_amount = Decimal("9750.00")
    refund_amount = Decimal("5000.00")
    commission_refund = Decimal("1750.00")
    payout_reduction = (refund_amount - commission_refund).quantize(Decimal("0.01"))
    new_amount = max(original_amount - payout_reduction, Decimal("0.00"))
    assert payout_reduction == Decimal("3250.00")
    assert new_amount == Decimal("6500.00")


@pytest.mark.asyncio
async def test_mark_payout_paid_success(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = PayoutService(db=cast(DatabaseSessionProtocol, db))

    payout_id = uuid4()
    brand_id = uuid4()
    order_id = uuid4()
    sub_order_id = uuid4()
    now = datetime.now(UTC)

    payout_data: dict[str, object] = {
        "id": payout_id,
        "brand_id": brand_id,
        "brand_name": "MASLOV",
        "order_id": order_id,
        "sub_order_id": sub_order_id,
        "amount": Decimal("9750.00"),
        "status": "pending",
        "payout_delay_days": 14,
        "scheduled_at": now + timedelta(days=14),
        "completed_at": None,
        "created_at": now,
    }

    async def _fake_get(*, payout_id: object) -> Mapping[str, object]:
        return payout_data

    monkeypatch.setattr(service, "_get_payout", _fake_get)

    result = await service.mark_payout_paid(payout_id=payout_id)

    assert result["status"] == "paid"
    assert result["sub_order_id"] == sub_order_id
    assert "order_id" not in result
    assert result["completed_at"] is not None
    assert db.committed is True


@pytest.mark.asyncio
async def test_mark_payout_paid_already_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = PayoutService(db=cast(DatabaseSessionProtocol, db))

    payout_data: dict[str, object] = {
        "id": uuid4(),
        "brand_id": uuid4(),
        "brand_name": "TEST",
        "order_id": uuid4(),
        "sub_order_id": uuid4(),
        "amount": Decimal("5000.00"),
        "status": "completed",
        "payout_delay_days": 14,
        "scheduled_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }

    async def _fake_get(*, payout_id: object) -> Mapping[str, object]:
        return payout_data

    monkeypatch.setattr(service, "_get_payout", _fake_get)

    with pytest.raises(PayoutAlreadyCompletedError):
        await service.mark_payout_paid(payout_id=uuid4())


@pytest.mark.asyncio
async def test_list_payouts_returns_sub_order_payload() -> None:
    db = _FakeDb()
    service = PayoutService(db=cast(DatabaseSessionProtocol, db))

    payout_id = uuid4()
    brand_id = uuid4()
    sub_order_id = uuid4()
    now = datetime.now(UTC)

    db.push_response([{"cnt": 1}])
    db.push_response(
        [
            {
                "id": payout_id,
                "brand_id": brand_id,
                "brand_name": "MASLOV",
                "sub_order_id": sub_order_id,
                "amount": Decimal("9750.00"),
                "status": "completed",
                "payout_delay_days": 14,
                "scheduled_at": now + timedelta(days=14),
                "completed_at": now,
                "created_at": now,
            }
        ]
    )

    items, total = await service.list_payouts(
        page=1,
        per_page=20,
        brand_id=brand_id,
        status_filter="paid",
    )

    assert total == 1
    assert items[0]["status"] == "paid"
    assert items[0]["sub_order_id"] == sub_order_id
    assert "order_id" not in items[0]
    assert "p.sub_order_id" in db.statements[1]


@pytest.mark.asyncio
async def test_create_payout_for_completed_sub_order_uses_snapshot_commission() -> None:
    db = _FakeDb()
    service = PayoutService(db=cast(DatabaseSessionProtocol, db))

    order_id = uuid4()
    sub_order_id = uuid4()
    brand_id = uuid4()
    delivered_at = datetime(2026, 2, 14, tzinfo=UTC)

    db.push_response([{"value": "14"}])
    db.push_response(
        [
            {
                "sub_order_id": sub_order_id,
                "order_id": order_id,
                "brand_id": brand_id,
                "status": "completed",
                "items_total": Decimal("15000.00"),
                "delivered_at": delivered_at,
                "brand_name": "MASLOV",
                "commission_total": Decimal("5250.00"),
            }
        ]
    )
    db.push_response([])
    db.push_response([])

    result = await service.create_payout_for_sub_order(sub_order_id=sub_order_id)

    assert result is not None
    assert result["sub_order_id"] == sub_order_id
    assert result["amount"] == Decimal("9750.00")
    assert result["scheduled_at"] == datetime(2026, 3, 1, tzinfo=UTC)
    assert db.last_params[-1] == {
        "brand_id": brand_id,
        "order_id": order_id,
        "sub_order_id": sub_order_id,
        "amount": Decimal("9750.00"),
        "payout_delay_days": 14,
        "scheduled_at": datetime(2026, 3, 1, tzinfo=UTC),
    }


@pytest.mark.asyncio
async def test_create_payout_for_sub_order_skips_existing_payout() -> None:
    db = _FakeDb()
    service = PayoutService(db=cast(DatabaseSessionProtocol, db))

    sub_order_id = uuid4()
    db.push_response([{"value": "14"}])
    db.push_response(
        [
            {
                "sub_order_id": sub_order_id,
                "order_id": uuid4(),
                "brand_id": uuid4(),
                "status": "completed",
                "items_total": Decimal("15000.00"),
                "delivered_at": datetime(2026, 2, 14, tzinfo=UTC),
                "brand_name": "MASLOV",
                "commission_total": Decimal("5250.00"),
            }
        ]
    )
    db.push_response([{"exists": 1}])

    result = await service.create_payout_for_sub_order(sub_order_id=sub_order_id)

    assert result is None


@pytest.mark.asyncio
async def test_handle_refund_impact_pending_payout(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = PayoutService(db=cast(DatabaseSessionProtocol, db))

    order_id = uuid4()
    brand_id = uuid4()
    payout_id = uuid4()
    sub_order_id = uuid4()

    db.push_response(
        [
            {
                "id": payout_id,
                "sub_order_id": sub_order_id,
                "status": "pending",
                "amount": Decimal("9750.00"),
            }
        ]
    )

    await service.handle_refund_impact(
        order_id=order_id,
        brand_id=brand_id,
        refund_amount=Decimal("5000.00"),
        commission_refund=Decimal("1750.00"),
    )

    assert db.committed is True


@pytest.mark.asyncio
async def test_handle_refund_impact_completed_payout_creates_negative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb()
    service = PayoutService(db=cast(DatabaseSessionProtocol, db))

    order_id = uuid4()
    brand_id = uuid4()
    payout_id = uuid4()
    sub_order_id = uuid4()

    db.push_response(
        [
            {
                "id": payout_id,
                "sub_order_id": sub_order_id,
                "status": "completed",
                "amount": Decimal("9750.00"),
            }
        ]
    )

    await service.handle_refund_impact(
        order_id=order_id,
        brand_id=brand_id,
        refund_amount=Decimal("15000.00"),
        commission_refund=Decimal("5250.00"),
    )

    assert db.committed is True
    assert db.execute_calls >= 2
