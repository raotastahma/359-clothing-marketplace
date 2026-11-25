from __future__ import annotations

# pyright: reportPrivateUsage=false
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest

from app.services.order_action_service import (
    DatabaseSessionProtocol as OrderActionDatabaseSessionProtocol,
)
from app.services.order_action_service import (
    OrderActionService,
    TokenGoneError,
)
from app.services.order_service import DatabaseSessionProtocol as OrderDatabaseSessionProtocol
from app.services.order_service import InvalidTransitionError, OrderService


class _FakeMappingResult:
    def __init__(self, rows: list[Mapping[str, object]] | None = None) -> None:
        self._rows = rows if rows is not None else []

    def first(self) -> Mapping[str, object] | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Mapping[str, object]]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[Mapping[str, object]] | None = None) -> None:
        self._rows = rows if rows is not None else []

    def mappings(self) -> _FakeMappingResult:
        return _FakeMappingResult(self._rows)

    def scalar_one_or_none(self) -> object:
        row = self._rows[0] if self._rows else None
        if row is None:
            return None
        return next(iter(row.values()), None)


class _FakeDb:
    def __init__(self, responses: list[_FakeResult]) -> None:
        self._responses = list(responses)
        self.statements: list[str] = []
        self.execute_params: list[Mapping[str, object] | None] = []
        self.commit_calls = 0

    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _FakeResult:
        _ = statement
        self.statements.append(str(statement))
        self.execute_params.append(params)
        if self._responses:
            return self._responses.pop(0)
        return _FakeResult()

    async def commit(self) -> None:
        self.commit_calls += 1


class _FakeOrderService(OrderService):
    def __init__(self, *, db: OrderDatabaseSessionProtocol) -> None:
        super().__init__(db=db)
        self.transition_calls: list[dict[str, object]] = []
        self.sync_calls: list[dict[str, object]] = []
        self.cancel_calls: list[dict[str, object]] = []

    async def transition_order(self, **kwargs: object) -> dict[str, object]:
        self.transition_calls.append(dict(kwargs))
        return {
            "id": kwargs["order_id"],
            "status": kwargs["target_status"],
            "tracking_number": kwargs.get("tracking_number"),
            "paid_at": None,
            "shipped_at": None,
            "delivered_at": None,
        }

    async def sync_order_status_from_sub_orders(self, **kwargs: object) -> dict[str, object]:
        self.sync_calls.append(dict(kwargs))
        return {
            "id": kwargs["order_id"],
            "status": "shipped" if kwargs.get("tracking_number") else "paid",
            "tracking_number": kwargs.get("tracking_number"),
            "paid_at": None,
            "shipped_at": None,
            "delivered_at": None,
        }

    async def handle_sub_order_cancelled_by_brand(self, **kwargs: object) -> dict[str, object]:
        self.cancel_calls.append(dict(kwargs))
        return {
            "id": kwargs["order_id"],
            "status": "paid",
            "tracking_number": None,
            "paid_at": None,
            "shipped_at": None,
            "delivered_at": None,
        }


@pytest.mark.asyncio
async def test_confirm_syncs_parent_order_from_sub_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb(responses=[])
    service = OrderActionService(
        db=cast(OrderActionDatabaseSessionProtocol, db),
        order_service=cast(
            OrderService,
            _FakeOrderService(db=cast(OrderDatabaseSessionProtocol, db)),
        ),
    )
    order_id = uuid4()
    consume_calls: list[dict[str, object]] = []

    async def _fake_consume(**kwargs: object) -> Mapping[str, object]:
        consume_calls.append(dict(kwargs))
        return {
            "order_id": order_id,
            "sub_order_id": uuid4(),
            "brand_id": uuid4(),
            "id": uuid4(),
            "action_type": "confirm",
        }

    monkeypatch.setattr(service, "_consume_token", _fake_consume)

    result = await service.confirm(token="token-confirm")

    assert result.order_id == order_id
    assert result.status == "paid"
    assert consume_calls == [
        {
            "token": "token-confirm",
            "expected_action_type": "confirm",
            "allowed_sub_order_statuses": frozenset({"paid"}),
            "target_status": "processing",
        }
    ]
    assert cast(_FakeOrderService, service._order_service).transition_calls == []
    assert cast(_FakeOrderService, service._order_service).sync_calls[0]["commit"] is False
    assert db.commit_calls == 1


@pytest.mark.asyncio
async def test_confirm_keeps_parent_paid_for_processing_sub_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb(responses=[])
    service = OrderActionService(
        db=cast(OrderActionDatabaseSessionProtocol, db),
        order_service=cast(
            OrderService,
            _FakeOrderService(db=cast(OrderDatabaseSessionProtocol, db)),
        ),
    )
    order_id = uuid4()
    consume_calls: list[dict[str, object]] = []

    async def _fake_consume(**kwargs: object) -> Mapping[str, object]:
        consume_calls.append(dict(kwargs))
        return {
            "order_id": order_id,
            "sub_order_id": uuid4(),
            "brand_id": uuid4(),
            "id": uuid4(),
            "action_type": "confirm",
        }

    monkeypatch.setattr(service, "_consume_token", _fake_consume)

    result = await service.confirm(token="token-confirm")

    assert result.order_id == order_id
    assert result.status == "paid"
    assert "processing" in result.message
    assert consume_calls == [
        {
            "token": "token-confirm",
            "expected_action_type": "confirm",
            "allowed_sub_order_statuses": frozenset({"paid"}),
            "target_status": "processing",
        }
    ]
    assert cast(_FakeOrderService, service._order_service).transition_calls == []
    assert cast(_FakeOrderService, service._order_service).sync_calls[0]["commit"] is False


@pytest.mark.asyncio
async def test_ship_updates_sub_order_before_parent_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb(responses=[])
    service = OrderActionService(
        db=cast(OrderActionDatabaseSessionProtocol, db),
        order_service=cast(
            OrderService,
            _FakeOrderService(db=cast(OrderDatabaseSessionProtocol, db)),
        ),
    )
    order_id = uuid4()
    consume_calls: list[dict[str, object]] = []

    async def _fake_consume(**kwargs: object) -> Mapping[str, object]:
        consume_calls.append(dict(kwargs))
        return {
            "order_id": order_id,
            "sub_order_id": uuid4(),
            "brand_id": uuid4(),
            "id": uuid4(),
            "action_type": "ship",
        }

    monkeypatch.setattr(service, "_consume_token", _fake_consume)

    result = await service.ship(token="token-ship", tracking_number=" YD-123456789 ")

    assert result.order_id == order_id
    assert result.status == "shipped"
    assert consume_calls == [
        {
            "token": "token-ship",
            "expected_action_type": "ship",
            "allowed_sub_order_statuses": frozenset({"processing"}),
            "target_status": "shipped",
            "tracking_number": "YD-123456789",
        }
    ]
    assert cast(_FakeOrderService, service._order_service).transition_calls == []
    assert (
        cast(_FakeOrderService, service._order_service).sync_calls[0]["tracking_number"]
        == "YD-123456789"
    )


@pytest.mark.asyncio
async def test_cancel_passes_previous_sub_order_status_for_refund(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb(responses=[])
    order_service = _FakeOrderService(db=cast(OrderDatabaseSessionProtocol, db))
    service = OrderActionService(
        db=cast(OrderActionDatabaseSessionProtocol, db),
        order_service=cast(OrderService, order_service),
    )
    order_id = uuid4()
    brand_id = uuid4()

    async def _fake_consume(**kwargs: object) -> Mapping[str, object]:
        _ = kwargs
        return {
            "order_id": order_id,
            "sub_order_id": uuid4(),
            "brand_id": brand_id,
            "id": uuid4(),
            "action_type": "cancel",
            "previous_sub_order_status": "processing",
            "sub_order_status": "cancelled_by_brand",
        }

    monkeypatch.setattr(service, "_consume_token", _fake_consume)

    result = await service.cancel(token="token-cancel")

    assert result.order_id == order_id
    assert order_service.cancel_calls[0]["brand_id"] == brand_id
    assert order_service.cancel_calls[0]["refund_from_status"] == "processing"
    assert order_service.cancel_calls[0]["commit"] is False


@pytest.mark.asyncio
async def test_consume_token_updates_sub_order_and_token_in_one_statement() -> None:
    token_row = {
        "id": uuid4(),
        "order_id": uuid4(),
        "sub_order_id": uuid4(),
        "brand_id": uuid4(),
        "action_type": "confirm",
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "used_at": None,
        "sub_order_status": "paid",
    }
    consumed_row = {**token_row, "used_at": datetime.now(UTC), "sub_order_status": "processing"}
    db = _FakeDb(responses=[_FakeResult([token_row]), _FakeResult([consumed_row])])
    service = OrderActionService(
        db=cast(OrderActionDatabaseSessionProtocol, db),
        order_service=cast(
            OrderService,
            _FakeOrderService(db=cast(OrderDatabaseSessionProtocol, db)),
        ),
    )

    result = await service._consume_token(
        token="confirm",
        expected_action_type="confirm",
        allowed_sub_order_statuses=frozenset({"paid"}),
        target_status="processing",
    )

    assert result == consumed_row
    assert "WITH token_row AS" in db.statements[1]
    assert "UPDATE sub_orders so" in db.statements[1]
    assert "AND so.status = tr.sub_order_status" in db.statements[1]
    assert "UPDATE order_action_tokens oat" in db.statements[1]
    params = db.execute_params[1]
    assert params is not None
    assert params["token_id"] == token_row["id"]
    assert params["allowed_status_0"] == "paid"
    assert params["confirmed_at"] is not None
    assert params["shipping_deadline"] is not None


@pytest.mark.asyncio
async def test_consume_token_sets_ship_tracking_and_timestamp_atomically() -> None:
    token_row = {
        "id": uuid4(),
        "order_id": uuid4(),
        "sub_order_id": uuid4(),
        "brand_id": uuid4(),
        "action_type": "ship",
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "used_at": None,
        "sub_order_status": "processing",
    }
    consumed_row = {**token_row, "used_at": datetime.now(UTC), "sub_order_status": "shipped"}
    db = _FakeDb(responses=[_FakeResult([token_row]), _FakeResult([consumed_row])])
    service = OrderActionService(
        db=cast(OrderActionDatabaseSessionProtocol, db),
        order_service=cast(
            OrderService,
            _FakeOrderService(db=cast(OrderDatabaseSessionProtocol, db)),
        ),
    )

    result = await service._consume_token(
        token="ship",
        expected_action_type="ship",
        allowed_sub_order_statuses=frozenset({"processing"}),
        target_status="shipped",
        tracking_number=" YD-123456789 ",
    )

    assert result == consumed_row
    assert "WITH token_row AS" in db.statements[1]
    params = db.execute_params[1]
    assert params is not None
    assert params["tracking_number"] == "YD-123456789"
    assert params["shipped_at"] is not None


@pytest.mark.asyncio
async def test_consume_token_rejects_expired_token() -> None:
    token_row = {
        "id": uuid4(),
        "order_id": uuid4(),
        "sub_order_id": uuid4(),
        "brand_id": uuid4(),
        "action_type": "confirm",
        "expires_at": datetime.now(UTC) - timedelta(hours=1),
        "used_at": None,
        "sub_order_status": "paid",
    }
    db = _FakeDb(responses=[_FakeResult([token_row])])
    service = OrderActionService(
        db=cast(OrderActionDatabaseSessionProtocol, db),
        order_service=cast(
            OrderService,
            _FakeOrderService(db=cast(OrderDatabaseSessionProtocol, db)),
        ),
    )

    with pytest.raises(TokenGoneError):
        await service._consume_token(
            token="expired",
            expected_action_type="confirm",
            allowed_sub_order_statuses=frozenset({"paid"}),
            target_status="processing",
        )


@pytest.mark.asyncio
async def test_consume_token_rejects_invalid_sub_order_status_without_marking_used() -> None:
    token_row = {
        "id": uuid4(),
        "order_id": uuid4(),
        "sub_order_id": uuid4(),
        "brand_id": uuid4(),
        "action_type": "ship",
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "used_at": None,
        "sub_order_status": "paid",
    }
    db = _FakeDb(responses=[_FakeResult([token_row])])
    service = OrderActionService(
        db=cast(OrderActionDatabaseSessionProtocol, db),
        order_service=cast(
            OrderService,
            _FakeOrderService(db=cast(OrderDatabaseSessionProtocol, db)),
        ),
    )

    with pytest.raises(InvalidTransitionError):
        await service._consume_token(
            token="ship-too-early",
            expected_action_type="ship",
            allowed_sub_order_statuses=frozenset({"processing"}),
            target_status="shipped",
        )

    assert len(db.statements) == 1


@pytest.mark.asyncio
async def test_consume_token_rejects_raced_sub_order_status_change() -> None:
    token_row = {
        "id": uuid4(),
        "order_id": uuid4(),
        "sub_order_id": uuid4(),
        "brand_id": uuid4(),
        "action_type": "cancel",
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "used_at": None,
        "sub_order_status": "paid",
    }
    refreshed_row = {**token_row, "sub_order_status": "processing"}
    db = _FakeDb(
        responses=[
            _FakeResult([token_row]),
            _FakeResult([]),
            _FakeResult([refreshed_row]),
        ]
    )
    service = OrderActionService(
        db=cast(OrderActionDatabaseSessionProtocol, db),
        order_service=cast(
            OrderService,
            _FakeOrderService(db=cast(OrderDatabaseSessionProtocol, db)),
        ),
    )

    with pytest.raises(InvalidTransitionError):
        await service._consume_token(
            token="cancel-race",
            expected_action_type="cancel",
            allowed_sub_order_statuses=frozenset({"paid"}),
            target_status="cancelled_by_brand",
        )

    assert len(db.statements) == 3
    assert "WITH token_row AS" in db.statements[1]
    assert "AND so.status = tr.sub_order_status" in db.statements[1]
