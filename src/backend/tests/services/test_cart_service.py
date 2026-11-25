from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from uuid import UUID, uuid4

import pytest
from beartype import beartype

from app.services.cart_service import (
    CartItemNotFoundError,
    CartService,
    DatabaseSessionProtocol,
    InsufficientStockError,
)


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


class _FakeDb:
    def __init__(self, responses: list[_FakeResult]) -> None:
        self._responses = list(responses)
        self.execute_calls: list[tuple[str, Mapping[str, object] | None]] = []
        self.committed = False

    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _FakeResult:
        sql = str(statement)
        self.execute_calls.append((sql, params))
        if self._responses:
            return self._responses.pop(0)
        return _FakeResult()

    async def commit(self) -> None:
        self.committed = True


@beartype
def _variant_snapshot(*, stock_quantity: int) -> Mapping[str, object]:
    return {
        "id": uuid4(),
        "stock_quantity": stock_quantity,
        "variant_is_active": True,
        "product_is_active": True,
        "brand_is_active": True,
    }


@pytest.mark.asyncio
async def test_add_item_merges_existing_quantity(monkeypatch: pytest.MonkeyPatch) -> None:
    cart_item_id = uuid4()
    db = _FakeDb(
        responses=[
            _FakeResult([{"id": cart_item_id, "quantity": 2}]),
            _FakeResult(),
        ]
    )
    service = CartService(db=cast(DatabaseSessionProtocol, db))
    user_id = uuid4()
    variant_id = uuid4()

    async def _fake_variant(*, product_variant_id: UUID) -> Mapping[str, object]:
        _ = product_variant_id
        return _variant_snapshot(stock_quantity=10)

    async def _fake_get_cart(*, user_id: UUID) -> dict[str, object]:
        _ = user_id
        return {"items": [], "total": 0, "items_count": 0}

    monkeypatch.setattr(service, "_get_variant_snapshot", _fake_variant)
    monkeypatch.setattr(service, "get_cart", _fake_get_cart)

    result = await service.add_item(user_id=user_id, product_variant_id=variant_id, quantity=3)

    assert result["items_count"] == 0
    assert db.committed is True
    assert len(db.execute_calls) == 2
    update_params = db.execute_calls[1][1]
    assert update_params is not None
    quantity_value = update_params["quantity"]
    assert isinstance(quantity_value, int)
    assert quantity_value == 5


@pytest.mark.asyncio
async def test_add_item_raises_for_insufficient_stock(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb(
        responses=[
            _FakeResult([{"id": uuid4(), "quantity": 3}]),
        ]
    )
    service = CartService(db=cast(DatabaseSessionProtocol, db))

    async def _fake_variant(*, product_variant_id: UUID) -> Mapping[str, object]:
        _ = product_variant_id
        return _variant_snapshot(stock_quantity=4)

    monkeypatch.setattr(service, "_get_variant_snapshot", _fake_variant)

    with pytest.raises(InsufficientStockError):
        await service.add_item(
            user_id=uuid4(),
            product_variant_id=uuid4(),
            quantity=2,
        )


@pytest.mark.asyncio
async def test_update_item_quantity_updates_cart(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb(responses=[_FakeResult()])
    service = CartService(db=cast(DatabaseSessionProtocol, db))
    user_id = uuid4()
    item_id = uuid4()
    variant_id = uuid4()

    async def _fake_get_item(*, user_id: UUID, cart_item_id: UUID) -> Mapping[str, object]:
        _ = user_id
        _ = cart_item_id
        return {"id": item_id, "product_variant_id": variant_id, "quantity": 1}

    async def _fake_variant(*, product_variant_id: UUID) -> Mapping[str, object]:
        _ = product_variant_id
        return _variant_snapshot(stock_quantity=8)

    async def _fake_get_cart(*, user_id: UUID) -> dict[str, object]:
        _ = user_id
        return {"items": [], "total": 0, "items_count": 0}

    monkeypatch.setattr(service, "_get_cart_item", _fake_get_item)
    monkeypatch.setattr(service, "_get_variant_snapshot", _fake_variant)
    monkeypatch.setattr(service, "get_cart", _fake_get_cart)

    await service.update_item_quantity(user_id=user_id, cart_item_id=item_id, quantity=4)

    assert db.committed is True
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_remove_item_raises_when_item_not_found() -> None:
    db = _FakeDb(responses=[_FakeResult()])
    service = CartService(db=cast(DatabaseSessionProtocol, db))

    with pytest.raises(CartItemNotFoundError):
        await service.remove_item(user_id=uuid4(), cart_item_id=uuid4())
