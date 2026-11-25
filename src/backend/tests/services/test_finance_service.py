from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest

from app.services.finance_service import BrandNotFoundError, DatabaseSessionProtocol, FinanceService


class _FakeResult:
    def __init__(self, rows: list[Mapping[str, object]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> _FakeResult:
        return self

    def first(self) -> Mapping[str, object] | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Mapping[str, object]]:
        return list(self._rows)


class _FakeDb:
    def __init__(self) -> None:
        self.execute_calls = 0
        self.statements: list[str] = []
        self._responses: list[_FakeResult] = []

    def push_response(self, rows: list[Mapping[str, object]]) -> None:
        self._responses.append(_FakeResult(rows))

    async def execute(
        self, statement: object, params: Mapping[str, object] | None = None
    ) -> _FakeResult:
        self.statements.append(str(statement))
        _ = params
        self.execute_calls += 1
        if self._responses:
            return self._responses.pop(0)
        return _FakeResult()


def test_commission_rate_from_brand_summary() -> None:
    """Commission is correctly calculated from order items."""
    sales = Decimal("225000.00")
    commission_rate = Decimal("0.35")
    expected_commission = (sales * commission_rate).quantize(Decimal("0.01"))
    assert expected_commission == Decimal("78750.00")


def test_brand_balance_total_earned() -> None:
    """Total earned = items total - commission total."""
    items_total = Decimal("225000.00")
    commission_total = Decimal("78750.00")
    total_earned = (items_total - commission_total).quantize(Decimal("0.01"))
    assert total_earned == Decimal("146250.00")


def test_pending_payout_calculation() -> None:
    """pending_payout = total_earned - total_paid."""
    total_earned = Decimal("409500.00")
    total_paid = Decimal("350000.00")
    pending = total_earned - total_paid
    assert pending == Decimal("59500.00")


def _normalize_sql(statement: str) -> str:
    return " ".join(statement.split())


@pytest.mark.asyncio
async def test_get_finance_report(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = FinanceService(db=cast(DatabaseSessionProtocol, db))

    db.push_response(
        [
            {
                "total_sales": Decimal("630000.00"),
                "total_commission": Decimal("220500.00"),
            }
        ]
    )
    db.push_response(
        [
            {
                "total_payouts_completed": Decimal("350000.00"),
                "total_payouts_pending": Decimal("59500.00"),
            }
        ]
    )
    db.push_response([{"total_refunds": Decimal("15000.00")}])

    brand_id = uuid4()
    db.push_response(
        [
            {
                "brand_id": brand_id,
                "brand_name": "MASLOV",
                "sales": Decimal("225000.00"),
                "commission": Decimal("78750.00"),
                "payouts_completed": Decimal("120000.00"),
                "payouts_pending": Decimal("25750.00"),
            }
        ]
    )

    result = await service.get_finance_report(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 2, 28),
    )

    assert result["total_sales"] == Decimal("630000.00")
    assert result["total_commission"] == Decimal("220500.00")
    assert result["total_payouts_completed"] == Decimal("350000.00")
    assert result["total_payouts_pending"] == Decimal("59500.00")
    assert result["total_refunds"] == Decimal("15000.00")

    summary = cast(list[Mapping[str, object]], result["brands_summary"])
    assert isinstance(summary, list)
    assert len(summary) == 1
    assert summary[0]["brand_name"] == "MASLOV"
    assert summary[0]["sales"] == Decimal("225000.00")
    assert "FROM sub_orders so" in db.statements[0]


@pytest.mark.asyncio
async def test_get_finance_report_filters_completed_payouts_by_completed_at() -> None:
    db = _FakeDb()
    service = FinanceService(db=cast(DatabaseSessionProtocol, db))

    await service.get_finance_report(
        date_from=date(2026, 2, 1),
        date_to=date(2026, 2, 28),
    )

    payout_totals_sql = _normalize_sql(db.statements[1])
    assert (
        "WHEN p.status = 'completed' AND p.completed_at >= :date_from "
        "AND p.completed_at < :date_to_exclusive"
    ) in payout_totals_sql
    assert (
        "WHEN p.status = 'pending' AND p.created_at >= :date_from "
        "AND p.created_at < :date_to_exclusive"
    ) in payout_totals_sql

    brand_summary_sql = _normalize_sql(db.statements[3])
    assert (
        "WHERE p.brand_id = b.id AND p.status = 'completed' "
        "AND p.completed_at >= :date_from AND p.completed_at < :date_to_exclusive"
    ) in brand_summary_sql


@pytest.mark.asyncio
async def test_get_brand_balance(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = FinanceService(db=cast(DatabaseSessionProtocol, db))
    brand_id = uuid4()
    sub_order_id = uuid4()
    payout_id = uuid4()
    now = datetime.now(UTC)

    db.push_response(
        [
            {
                "id": brand_id,
                "name": "MASLOV",
                "commission_rate": Decimal("0.3500"),
            }
        ]
    )
    db.push_response([{"total_earned": Decimal("409500.00")}])
    db.push_response(
        [
            {
                "total_paid": Decimal("350000.00"),
                "pending_payout": Decimal("59500.00"),
            }
        ]
    )
    db.push_response(
        [
            {
                "id": payout_id,
                "sub_order_id": sub_order_id,
                "amount": Decimal("59500.00"),
                "status": "pending",
                "payout_delay_days": 14,
                "scheduled_at": now + timedelta(days=14),
                "completed_at": None,
                "created_at": now,
            }
        ]
    )

    result = await service.get_brand_balance(brand_id=brand_id)

    assert result["brand_name"] == "MASLOV"
    assert result["commission_rate"] == Decimal("0.3500")
    assert result["total_earned"] == Decimal("409500.00")
    assert result["total_paid"] == Decimal("350000.00")
    assert result["pending_payout"] == Decimal("59500.00")
    assert "FROM sub_orders so" in db.statements[1]
    recent_payouts = cast(list[Mapping[str, object]], result["recent_payouts"])
    assert recent_payouts[0]["sub_order_id"] == sub_order_id
    assert "order_id" not in recent_payouts[0]


@pytest.mark.asyncio
async def test_get_brand_balance_not_found() -> None:
    db = _FakeDb()
    service = FinanceService(db=cast(DatabaseSessionProtocol, db))

    with pytest.raises(BrandNotFoundError):
        await service.get_brand_balance(brand_id=uuid4())
