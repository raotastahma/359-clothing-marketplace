from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest

from app.services.brand_portal_finance_service import (
    BrandPortalFinanceService,
    DatabaseSessionProtocol,
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


class _FakeDb:
    def __init__(self) -> None:
        self._responses: list[_FakeResult] = []
        self.statements: list[str] = []
        self.params: list[Mapping[str, object] | None] = []

    def push_response(self, rows: list[Mapping[str, object]]) -> None:
        self._responses.append(_FakeResult(rows))

    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _FakeResult:
        self.statements.append(str(statement))
        self.params.append(params)
        if self._responses:
            return self._responses.pop(0)
        return _FakeResult()


def _service(db: _FakeDb) -> BrandPortalFinanceService:
    return BrandPortalFinanceService(db=cast(DatabaseSessionProtocol, db))


def _normalize_sql(statement: str) -> str:
    return " ".join(statement.split())


@pytest.mark.asyncio
async def test_get_analytics_summary_uses_snapshot_commission_totals() -> None:
    db = _FakeDb()
    brand_id = uuid4()
    db.push_response(
        [
            {
                "orders_count": 12,
                "total_sales": Decimal("180000.00"),
                "commission_total": Decimal("63000.00"),
            }
        ]
    )
    db.push_response(
        [
            {
                "payout_pending": Decimal("117000.00"),
                "payout_completed": Decimal("0.00"),
            }
        ]
    )

    result = await _service(db).get_analytics_summary(
        brand_id=brand_id,
        commission_rate=Decimal("0.3500"),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 2, 28),
    )

    assert result["orders_count"] == 12
    assert result["total_sales"] == Decimal("180000.00")
    assert result["commission_rate"] == Decimal("0.3500")
    assert result["commission_total"] == Decimal("63000.00")
    assert result["payout_pending"] == Decimal("117000.00")
    summary_sql = _normalize_sql(db.statements[0])
    assert "SUM(oi.commission_amount)" in summary_sql
    assert "so.brand_id = :brand_id" in summary_sql


@pytest.mark.asyncio
async def test_get_analytics_summary_returns_zeroes_for_empty_period() -> None:
    db = _FakeDb()

    result = await _service(db).get_analytics_summary(
        brand_id=uuid4(),
        commission_rate=Decimal("0.2750"),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
    )

    assert result["orders_count"] == 0
    assert result["total_sales"] == Decimal("0.00")
    assert result["commission_rate"] == Decimal("0.2750")
    assert result["commission_total"] == Decimal("0.00")
    assert result["payout_pending"] == Decimal("0.00")
    assert result["payout_completed"] == Decimal("0.00")


@pytest.mark.asyncio
async def test_get_top_products_returns_revenue_ordered_products() -> None:
    db = _FakeDb()
    product_id = uuid4()
    db.push_response(
        [
            {
                "product_id": product_id,
                "product_name": "Structured Jacket",
                "units_sold": 3,
                "total_sales": Decimal("45000.00"),
            }
        ]
    )

    result = await _service(db).get_top_products(
        brand_id=uuid4(),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 2, 28),
        limit=10,
    )

    assert result == [
        {
            "product_id": product_id,
            "product_name": "Structured Jacket",
            "units_sold": 3,
            "total_sales": Decimal("45000.00"),
        }
    ]
    assert "ORDER BY total_sales DESC" in _normalize_sql(db.statements[0])


@pytest.mark.asyncio
async def test_get_top_products_returns_empty_when_no_sales() -> None:
    db = _FakeDb()

    result = await _service(db).get_top_products(
        brand_id=uuid4(),
        date_from=date(2026, 1, 1),
        date_to=date(2026, 2, 28),
        limit=10,
    )

    assert result == []


@pytest.mark.asyncio
async def test_list_payouts_returns_brand_payload_with_commission_rate() -> None:
    db = _FakeDb()
    payout_id = uuid4()
    sub_order_id = uuid4()
    now = datetime.now(UTC)
    db.push_response([{"cnt": 1}])
    db.push_response(
        [
            {
                "id": payout_id,
                "sub_order_id": sub_order_id,
                "amount": Decimal("9750.00"),
                "commission_rate": Decimal("0.3500"),
                "status": "pending",
                "scheduled_at": now,
                "completed_at": None,
                "created_at": now,
            }
        ]
    )

    items, total = await _service(db).list_payouts(
        brand_id=uuid4(),
        page=1,
        per_page=20,
        status_filter="pending",
    )

    assert total == 1
    assert items[0]["id"] == payout_id
    assert items[0]["sub_order_id"] == sub_order_id
    assert items[0]["commission_rate"] == Decimal("0.3500")
    assert "order_id" not in items[0]
    assert "MAX(oi.commission_rate)" in _normalize_sql(db.statements[1])


@pytest.mark.asyncio
async def test_list_payouts_returns_empty_for_unknown_status() -> None:
    db = _FakeDb()

    items, total = await _service(db).list_payouts(
        brand_id=uuid4(),
        page=1,
        per_page=20,
        status_filter="refunded",
    )

    assert items == []
    assert total == 0
    assert db.statements == []
