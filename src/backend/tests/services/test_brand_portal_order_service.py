from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.services.brand_portal_order_service import (
    BrandPortalOrderNotFoundError,
    BrandPortalOrderService,
    DatabaseSessionProtocol,
)
from app.services.order_service import InvalidTransitionError, OrderService


class _FakeMappingResult:
    def __init__(self, rows: list[Mapping[str, object]] | None = None) -> None:
        self._rows = rows or []

    def first(self) -> Mapping[str, object] | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Mapping[str, object]]:
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows: list[Mapping[str, object]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> _FakeMappingResult:
        return _FakeMappingResult(self._rows)


class _FakeDb:
    def __init__(self) -> None:
        self._responses: list[_FakeResult] = []
        self.statements: list[str] = []
        self.params: list[Mapping[str, object] | None] = []
        self.commit_calls = 0

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

    async def commit(self) -> None:
        self.commit_calls += 1


class _FakeOrderService(OrderService):
    def __init__(self) -> None:
        self.sync_calls: list[dict[str, object]] = []

    async def sync_order_status_from_sub_orders(self, **kwargs: object) -> dict[str, object]:
        self.sync_calls.append(dict(kwargs))
        return {
            "id": kwargs["order_id"],
            "status": "paid",
            "tracking_number": kwargs.get("tracking_number"),
            "paid_at": None,
            "shipped_at": None,
            "delivered_at": None,
        }


def _service(
    db: _FakeDb, order_service: _FakeOrderService | None = None
) -> BrandPortalOrderService:
    return BrandPortalOrderService(
        db=cast(DatabaseSessionProtocol, db),
        order_service=cast(OrderService, order_service or _FakeOrderService()),
    )


def _sub_order_row(
    *,
    sub_order_id: UUID | None = None,
    order_id: UUID | None = None,
    brand_id: UUID | None = None,
    status: str = "paid",
    confirmation_deadline: datetime | None = None,
    shipping_deadline: datetime | None = None,
    delivery_address_json: dict[str, object] | None = None,
    tracking_number: str | None = None,
    confirmed_at: datetime | None = None,
    shipped_at: datetime | None = None,
) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "id": sub_order_id or uuid4(),
        "order_id": order_id or uuid4(),
        "brand_id": brand_id or uuid4(),
        "status": status,
        "items_total": Decimal("15000.00"),
        "commission_total": Decimal("5250.00"),
        "tracking_number": tracking_number,
        "confirmation_deadline": confirmation_deadline or now + timedelta(hours=1),
        "shipping_deadline": shipping_deadline or now + timedelta(hours=24),
        "confirmed_at": confirmed_at,
        "shipped_at": shipped_at,
        "created_at": now,
        "delivery_address_json": delivery_address_json,
    }


def _item_row(*, sub_order_id: UUID) -> dict[str, object]:
    return {
        "sub_order_id": sub_order_id,
        "product_name": "Structured Jacket",
        "size": "M",
        "quantity": 1,
        "unit_price": Decimal("15000.00"),
        "image_url": "https://storage.example/jacket.jpg",
    }


@pytest.mark.asyncio
async def test_list_brand_orders_maps_items_and_sla_status() -> None:
    db = _FakeDb()
    brand_id = uuid4()
    sub_order_id = uuid4()
    row = _sub_order_row(sub_order_id=sub_order_id, brand_id=brand_id)
    db.push_response([{"cnt": 1}])
    db.push_response([row])
    db.push_response([_item_row(sub_order_id=sub_order_id)])

    items, total = await _service(db).list_brand_orders(
        brand_id=brand_id,
        page=2,
        per_page=10,
        status_filter="paid",
    )

    assert total == 1
    assert db.params[1] is not None
    assert db.params[1]["brand_id"] == brand_id
    assert db.params[1]["offset"] == 10
    assert items[0]["id"] == sub_order_id
    assert items[0]["parent_order_id"] == row["order_id"]
    assert items[0]["sla_status"] == "at_risk"
    assert items[0]["payout_amount"] == Decimal("9750.00")
    assert cast(list[Mapping[str, object]], items[0]["items"])[0]["product_name"] == (
        "Structured Jacket"
    )


@pytest.mark.asyncio
async def test_list_brand_orders_returns_empty_for_unknown_status() -> None:
    db = _FakeDb()

    items, total = await _service(db).list_brand_orders(
        brand_id=uuid4(),
        page=1,
        per_page=20,
        status_filter="unknown",
    )

    assert items == []
    assert total == 0
    assert db.statements == []


@pytest.mark.asyncio
async def test_get_brand_order_detail_includes_delivery_address() -> None:
    db = _FakeDb()
    brand_id = uuid4()
    sub_order_id = uuid4()
    address: dict[str, object] = {"city": "Moscow", "street": "Tverskaya 1"}
    db.push_response(
        [
            _sub_order_row(
                sub_order_id=sub_order_id, brand_id=brand_id, delivery_address_json=address
            )
        ]
    )
    db.push_response([_item_row(sub_order_id=sub_order_id)])

    result = await _service(db).get_brand_order_detail(
        brand_id=brand_id,
        sub_order_id=sub_order_id,
    )

    assert result["id"] == sub_order_id
    assert result["delivery_address"] == address
    assert result["tracking_number"] is None
    assert cast(list[Mapping[str, object]], result["items"])[0]["size"] == "M"


@pytest.mark.asyncio
async def test_get_brand_order_detail_raises_not_found() -> None:
    db = _FakeDb()
    db.push_response([])

    with pytest.raises(BrandPortalOrderNotFoundError):
        await _service(db).get_brand_order_detail(
            brand_id=uuid4(),
            sub_order_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_confirm_sub_order_transitions_paid_to_processing() -> None:
    db = _FakeDb()
    order_service = _FakeOrderService()
    brand_id = uuid4()
    sub_order_id = uuid4()
    order_id = uuid4()
    confirmed_at = datetime.now(UTC)
    db.push_response(
        [
            _sub_order_row(
                sub_order_id=sub_order_id,
                order_id=order_id,
                brand_id=brand_id,
                status="processing",
                confirmed_at=confirmed_at,
            )
        ]
    )

    result = await _service(db, order_service).confirm_sub_order(
        brand_id=brand_id,
        sub_order_id=sub_order_id,
    )

    assert result["id"] == sub_order_id
    assert result["status"] == "processing"
    assert result["confirmed_at"] == confirmed_at
    assert order_service.sync_calls == [{"order_id": order_id, "commit": False}]
    assert db.commit_calls == 1
    assert db.params[0] is not None
    assert db.params[0]["expected_status"] == "paid"


@pytest.mark.asyncio
async def test_confirm_sub_order_raises_conflict_for_wrong_status() -> None:
    db = _FakeDb()
    brand_id = uuid4()
    sub_order_id = uuid4()
    db.push_response([])
    db.push_response(
        [_sub_order_row(sub_order_id=sub_order_id, brand_id=brand_id, status="shipped")]
    )

    with pytest.raises(InvalidTransitionError) as exc_info:
        await _service(db).confirm_sub_order(
            brand_id=brand_id,
            sub_order_id=sub_order_id,
        )

    assert exc_info.value.current_status == "shipped"
    assert exc_info.value.target_status == "processing"
    assert db.commit_calls == 0


@pytest.mark.asyncio
async def test_ship_sub_order_sets_tracking_and_syncs_parent() -> None:
    db = _FakeDb()
    order_service = _FakeOrderService()
    brand_id = uuid4()
    sub_order_id = uuid4()
    order_id = uuid4()
    shipped_at = datetime.now(UTC)
    db.push_response(
        [
            _sub_order_row(
                sub_order_id=sub_order_id,
                order_id=order_id,
                brand_id=brand_id,
                status="shipped",
                tracking_number="YD-123456789",
                shipped_at=shipped_at,
            )
        ]
    )

    result = await _service(db, order_service).ship_sub_order(
        brand_id=brand_id,
        sub_order_id=sub_order_id,
        tracking_number=" YD-123456789 ",
    )

    assert result["status"] == "shipped"
    assert result["tracking_number"] == "YD-123456789"
    assert result["shipped_at"] == shipped_at
    assert order_service.sync_calls == [
        {"order_id": order_id, "tracking_number": "YD-123456789", "commit": False}
    ]
    assert db.params[0] is not None
    assert db.params[0]["expected_status"] == "processing"
    assert db.params[0]["tracking_number"] == "YD-123456789"
    assert db.commit_calls == 1


@pytest.mark.asyncio
async def test_ship_sub_order_rejects_blank_tracking_number() -> None:
    db = _FakeDb()

    with pytest.raises(ValueError, match="tracking_number is required"):
        await _service(db).ship_sub_order(
            brand_id=uuid4(),
            sub_order_id=uuid4(),
            tracking_number="  ",
        )

    assert db.statements == []
