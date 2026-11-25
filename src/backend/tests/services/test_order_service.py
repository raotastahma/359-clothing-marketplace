from __future__ import annotations

# pyright: reportPrivateUsage=false
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest

from app.core.config import settings
from app.integrations.delivery.protocol import DeliveryEstimate, DeliveryProvider
from app.integrations.payments.protocol import PaymentProvider
from app.services.order_service import (
    ORDER_STATUSES,
    SUB_ORDER_TRANSITIONS,
    TRANSITIONS,
    DatabaseSessionProtocol,
    EmptyCartError,
    InsufficientStockError,
    InvalidTransitionError,
    OrderService,
    PaymentProviderNotConfiguredError,
)

VALID_TRANSITIONS = tuple(
    (current_status, target_status)
    for current_status, target_statuses in TRANSITIONS.items()
    for target_status in sorted(target_statuses)
)
VALID_SUB_ORDER_TRANSITIONS = tuple(
    (current_status, target_status)
    for current_status, target_statuses in SUB_ORDER_TRANSITIONS.items()
    for target_status in sorted(target_statuses)
)
INVALID_TRANSITIONS = tuple(
    (current_status, target_status)
    for current_status in sorted(ORDER_STATUSES)
    for target_status in sorted(ORDER_STATUSES)
    if current_status != target_status
    and target_status not in TRANSITIONS.get(current_status, frozenset())
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
        self.statements: list[str] = []
        self.execute_params: list[Mapping[str, object] | None] = []
        self._responses: list[_FakeResult] = []

    def push_response(self, rows: list[Mapping[str, object]]) -> None:
        self._responses.append(_FakeResult(rows))

    async def execute(
        self, statement: object, params: Mapping[str, object] | None = None
    ) -> _FakeResult:
        self.execute_calls += 1
        self.statements.append(str(statement))
        self.execute_params.append(params)
        if self._responses:
            return self._responses.pop(0)
        return _FakeResult()

    async def commit(self) -> None:
        self.committed = True


def _order_row(*, status: str) -> dict[str, object]:
    return {
        "id": uuid4(),
        "user_id": uuid4(),
        "status": status,
        "paid_at": None,
        "shipped_at": None,
        "delivered_at": None,
        "created_at": datetime.now(UTC),
        "buyer_email": "buyer@example.com",
        "buyer_name": "Buyer",
        "buyer_phone": "+79001234567",
        "delivery_address_json": {
            "city": "Moscow",
            "street": "Tverskaya 1",
            "apartment": "10",
            "postal_code": "125009",
        },
        "total_amount": 1000,
        "commission_total": 350,
        "customer_delivery_cost": 0,
    }


def _sub_order_row(
    *,
    order_id: object | None = None,
    brand_id: object | None = None,
    sub_order_id: object | None = None,
    status: str = "paid",
    actual_delivery_cost: Decimal = Decimal("0.00"),
    brand_name: str = "MASLOV",
    items_count: int = 1,
) -> dict[str, object]:
    return {
        "id": sub_order_id or uuid4(),
        "order_id": order_id or uuid4(),
        "brand_id": brand_id or uuid4(),
        "brand_name": brand_name,
        "status": status,
        "items_total": Decimal("800.00"),
        "commission_total": Decimal("280.00"),
        "actual_delivery_cost": actual_delivery_cost,
        "tracking_number": None,
        "confirmation_deadline": None,
        "shipping_deadline": None,
        "confirmed_at": None,
        "shipped_at": None,
        "delivered_at": None,
        "completed_at": None,
        "created_at": datetime.now(UTC),
        "items_count": items_count,
    }


@pytest.mark.parametrize(("current_status", "target_status"), VALID_TRANSITIONS)
@pytest.mark.asyncio
async def test_transition_order_allows_every_configured_transition(
    monkeypatch: pytest.MonkeyPatch,
    current_status: str,
    target_status: str,
) -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    initial = _order_row(status=current_status)
    updated = dict(initial)
    updated["status"] = target_status
    if target_status == "paid":
        updated["paid_at"] = datetime.now(UTC)
    if target_status == "shipped":
        updated["shipped_at"] = datetime.now(UTC)
    if target_status == "delivered":
        updated["delivered_at"] = datetime.now(UTC)

    order_calls = {"count": 0}

    async def _fake_get_order(*, order_id: object) -> Mapping[str, object]:
        _ = order_id
        order_calls["count"] += 1
        return initial if order_calls["count"] == 1 else updated

    async def _fake_release(*, order_id: object, brand_id: object) -> None:
        _ = order_id
        _ = brand_id
        return

    async def _fake_refund(*, order_id: object, from_status: str, brand_id: object) -> None:
        _ = order_id
        _ = from_status
        _ = brand_id
        return

    async def _fake_notify(*, order: Mapping[str, object], status: str) -> None:
        _ = order
        _ = status
        return

    monkeypatch.setattr(service, "_get_order_snapshot", _fake_get_order)
    monkeypatch.setattr(service, "_release_stock", _fake_release)
    monkeypatch.setattr(service, "_create_refunds", _fake_refund)
    monkeypatch.setattr(service, "_notify_buyer_status_change", _fake_notify)

    payload = await service.transition_order(
        order_id=uuid4(),
        target_status=target_status,
    )

    assert payload["status"] == target_status
    assert db.committed is True


@pytest.mark.parametrize(("current_status", "target_status"), INVALID_TRANSITIONS)
def test_validate_transition_rejects_every_non_configured_transition(
    current_status: str,
    target_status: str,
) -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))

    with pytest.raises(InvalidTransitionError):
        service._validate_transition(current_status=current_status, target_status=target_status)


@pytest.mark.parametrize(("current_status", "target_status"), VALID_SUB_ORDER_TRANSITIONS)
def test_sub_order_transitions_include_processing_flow(
    current_status: str,
    target_status: str,
) -> None:
    assert target_status in SUB_ORDER_TRANSITIONS[current_status]


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["processing", "processing"], "paid"),
        (["processing", "shipped"], "shipped"),
        (["delivered", "delivered"], "delivered"),
        (["completed", "completed"], "completed"),
    ],
)
def test_aggregate_order_status_from_sub_orders(
    statuses: list[str],
    expected: str,
) -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))

    assert service._aggregate_order_status_from_sub_orders(statuses=statuses) == expected


@pytest.mark.asyncio
async def test_sync_order_status_notifies_later_shipped_sub_order_when_parent_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    order_id = uuid4()
    tracking_number = "TRACK-SECOND"
    order_row = _order_row(status="shipped") | {"id": order_id}
    notified: list[dict[str, object]] = []

    db.push_response(
        [
            _sub_order_row(order_id=order_id, status="shipped"),
            _sub_order_row(order_id=order_id, status="processing"),
        ]
    )
    db.push_response([order_row])

    async def _fake_notify(
        *,
        order: Mapping[str, object],
        status: str,
        tracking_number: str | None = None,
    ) -> None:
        notified.append(
            {
                "order": order,
                "status": status,
                "tracking_number": tracking_number,
            }
        )

    monkeypatch.setattr(service, "_notify_buyer_status_change", _fake_notify)

    payload = await service.sync_order_status_from_sub_orders(
        order_id=order_id,
        tracking_number=tracking_number,
    )

    assert payload["status"] == "shipped"
    assert notified == [
        {
            "order": order_row,
            "status": "shipped",
            "tracking_number": tracking_number,
        }
    ]
    assert not any("UPDATE orders" in statement for statement in db.statements)


@pytest.mark.asyncio
async def test_transition_pending_to_cancelled_releases_stock_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    initial = _order_row(status="pending")
    updated = dict(initial)
    updated["status"] = "cancelled_by_buyer"

    order_calls = {"count": 0}
    called = {"release": 0, "refund": 0}

    async def _fake_get_order(*, order_id: object) -> Mapping[str, object]:
        _ = order_id
        order_calls["count"] += 1
        return initial if order_calls["count"] == 1 else updated

    async def _fake_release(*, order_id: object, brand_id: object) -> None:
        _ = order_id
        _ = brand_id
        called["release"] += 1

    async def _fake_refund(*, order_id: object, from_status: str, brand_id: object) -> None:
        _ = order_id
        _ = from_status
        _ = brand_id
        called["refund"] += 1

    async def _fake_notify(*, order: Mapping[str, object], status: str) -> None:
        _ = order
        _ = status
        return

    monkeypatch.setattr(service, "_get_order_snapshot", _fake_get_order)
    monkeypatch.setattr(service, "_release_stock", _fake_release)
    monkeypatch.setattr(service, "_create_refunds", _fake_refund)
    monkeypatch.setattr(service, "_notify_buyer_status_change", _fake_notify)

    payload = await service.transition_order(order_id=uuid4(), target_status="cancelled_by_buyer")

    assert payload["status"] == "cancelled_by_buyer"
    assert called["release"] == 1
    assert called["refund"] == 0
    assert db.committed is True


@pytest.mark.asyncio
async def test_transition_paid_to_cancelled_creates_refund(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    initial = _order_row(status="paid")
    updated = dict(initial)
    updated["status"] = "cancelled_by_buyer"

    order_calls = {"count": 0}
    called = {"refund": 0}

    async def _fake_get_order(*, order_id: object) -> Mapping[str, object]:
        _ = order_id
        order_calls["count"] += 1
        return initial if order_calls["count"] == 1 else updated

    async def _fake_release(*, order_id: object, brand_id: object) -> None:
        _ = order_id
        _ = brand_id
        return

    async def _fake_refund(*, order_id: object, from_status: str, brand_id: object) -> None:
        _ = order_id
        _ = from_status
        _ = brand_id
        called["refund"] += 1

    async def _fake_notify(*, order: Mapping[str, object], status: str) -> None:
        _ = order
        _ = status
        return

    monkeypatch.setattr(service, "_get_order_snapshot", _fake_get_order)
    monkeypatch.setattr(service, "_release_stock", _fake_release)
    monkeypatch.setattr(service, "_create_refunds", _fake_refund)
    monkeypatch.setattr(service, "_notify_buyer_status_change", _fake_notify)

    payload = await service.transition_order(order_id=uuid4(), target_status="cancelled_by_buyer")

    assert payload["status"] == "cancelled_by_buyer"
    assert called["refund"] == 1


@pytest.mark.asyncio
async def test_sub_order_cancel_refunds_when_parent_order_already_shipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    order_id = uuid4()
    brand_id = uuid4()
    called = {"refund": 0}

    async def _fake_get_order(*, order_id: object) -> Mapping[str, object]:
        _ = order_id
        return _order_row(status="shipped")

    async def _fake_release(*, order_id: object, brand_id: object) -> None:
        _ = order_id
        _ = brand_id
        return

    async def _fake_refund(*, order_id: object, from_status: str, brand_id: object) -> None:
        _ = order_id
        _ = brand_id
        assert from_status == "processing"
        called["refund"] += 1

    async def _fake_sync(**kwargs: object) -> dict[str, object]:
        assert kwargs["order_id"] == order_id
        return {"id": order_id, "status": "shipped"}

    monkeypatch.setattr(service, "_get_order_snapshot", _fake_get_order)
    monkeypatch.setattr(service, "_release_stock", _fake_release)
    monkeypatch.setattr(service, "_create_refunds", _fake_refund)
    monkeypatch.setattr(service, "sync_order_status_from_sub_orders", _fake_sync)

    payload = await service.handle_sub_order_cancelled_by_brand(
        order_id=order_id,
        brand_id=brand_id,
        refund_from_status="processing",
    )

    assert payload["status"] == "shipped"
    assert called["refund"] == 1


@pytest.mark.asyncio
async def test_invalid_transition_returns_conflict_error(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    initial = _order_row(status="processing")

    async def _fake_get_order(*, order_id: object) -> Mapping[str, object]:
        _ = order_id
        return initial

    monkeypatch.setattr(service, "_get_order_snapshot", _fake_get_order)

    with pytest.raises(InvalidTransitionError):
        await service.transition_order(order_id=uuid4(), target_status="cancelled_by_buyer")


@pytest.mark.asyncio
async def test_transition_shipped_to_delivered_does_not_create_payout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    initial = _order_row(status="shipped")
    updated = dict(initial)
    updated["status"] = "delivered"
    updated["delivered_at"] = datetime.now(UTC)

    order_calls = {"count": 0}

    async def _fake_get_order(*, order_id: object) -> Mapping[str, object]:
        _ = order_id
        order_calls["count"] += 1
        return initial if order_calls["count"] == 1 else updated

    async def _fake_notify(*, order: Mapping[str, object], status: str) -> None:
        _ = order
        _ = status
        return

    monkeypatch.setattr(service, "_get_order_snapshot", _fake_get_order)
    monkeypatch.setattr(service, "_notify_buyer_status_change", _fake_notify)

    payload = await service.transition_order(order_id=uuid4(), target_status="delivered")

    assert payload["status"] == "delivered"
    assert not any("INSERT INTO payouts" in statement for statement in db.statements)


@pytest.mark.asyncio
async def test_transition_order_can_skip_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    initial = _order_row(status="pending")
    updated = dict(initial)
    updated["status"] = "paid"
    updated["paid_at"] = datetime.now(UTC)

    order_calls = {"count": 0}

    async def _fake_get_order(*, order_id: object) -> Mapping[str, object]:
        _ = order_id
        order_calls["count"] += 1
        return initial if order_calls["count"] == 1 else updated

    monkeypatch.setattr(service, "_get_order_snapshot", _fake_get_order)

    payload = await service.transition_order(
        order_id=uuid4(),
        target_status="paid",
        notify_buyer=False,
        commit=False,
    )

    assert payload["status"] == "paid"
    assert db.committed is False
    assert db.execute_calls == 1


# ------------------------------------------------------------------
# Tests for create_order: commission calculation, stock, cart clear
# ------------------------------------------------------------------


def _cart_row(
    *,
    variant_id: object | None = None,
    brand_id: object | None = None,
    price_rub: Decimal = Decimal("15000.00"),
    commission_rate: Decimal = Decimal("0.3500"),
    quantity: int = 1,
    stock_quantity: int = 10,
) -> dict[str, object]:
    return {
        "cart_item_id": uuid4(),
        "quantity": quantity,
        "variant_id": variant_id or uuid4(),
        "product_id": uuid4(),
        "price_rub": price_rub,
        "stock_quantity": stock_quantity,
        "vendor_code": "MSL-JKT-001-M",
        "size": "M",
        "color": None,
        "variant_is_active": True,
        "product_is_active": True,
        "product_name": "Structured Jacket",
        "brand_id": brand_id or uuid4(),
        "commission_rate": commission_rate,
        "brand_is_active": True,
    }


def _address_row() -> dict[str, object]:
    return {
        "id": uuid4(),
        "city": "Москва",
        "street": "ул. Тверская, 1",
        "apartment": "кв. 10",
        "postal_code": "125009",
    }


class _FakePaymentProvider:
    def __init__(self) -> None:
        self.created = False
        self.return_url: str | None = None
        self.refunds: list[dict[str, object]] = []

    async def create_payment(
        self, *, amount: Decimal, order_id: object, return_url: str, description: str
    ) -> object:
        from app.integrations.payments.protocol import PaymentCreateResult

        self.created = True
        self.return_url = return_url
        return PaymentCreateResult(
            external_payment_id="ext-pay-123",
            payment_url="https://yookassa.ru/checkout/test",
            status="pending",
        )

    async def get_payment_status(self, *, external_payment_id: str) -> object:
        raise NotImplementedError

    async def create_refund(self, *, payment_id: str, amount: Decimal, reason: str) -> str:
        self.refunds.append({"payment_id": payment_id, "amount": amount, "reason": reason})
        return "refund-123"


class _FakeDeliveryProvider:
    def __init__(self) -> None:
        self.calculate_cost_called = False
        self.calculate_cost_calls: list[dict[str, object]] = []

    async def calculate_cost(
        self,
        *,
        address: dict[str, str],
        weight_kg: float,
        dimensions: dict[str, float],
    ) -> DeliveryEstimate:
        self.calculate_cost_called = True
        self.calculate_cost_calls.append(
            {
                "address": address,
                "weight_kg": weight_kg,
                "dimensions": dimensions,
            }
        )
        return DeliveryEstimate(cost=Decimal("500.00"), estimated_days=3)

    async def create_shipment(
        self, *, order_id: object, address: dict[str, str], items: list[dict[str, object]]
    ) -> object:
        _ = order_id
        _ = address
        _ = items
        raise NotImplementedError

    async def get_tracking_status(self, *, tracking_number: str) -> str:
        _ = tracking_number
        raise NotImplementedError


def test_commission_calculation_single_item() -> None:
    unit_price = Decimal("15000.00")
    quantity = 1
    commission_rate = Decimal("0.3500")

    item_total = (unit_price * Decimal(quantity)).quantize(Decimal("0.01"))
    commission_amount = (item_total * commission_rate).quantize(Decimal("0.01"))

    assert item_total == Decimal("15000.00")
    assert commission_amount == Decimal("5250.00")


def test_commission_calculation_multiple_items() -> None:
    items: list[dict[str, Decimal | int]] = [
        {"price": Decimal("15000.00"), "qty": 2, "rate": Decimal("0.3500")},
        {"price": Decimal("8000.00"), "qty": 1, "rate": Decimal("0.2500")},
    ]
    total_amount = Decimal("0.00")
    commission_total = Decimal("0.00")

    for item in items:
        item_total = (item["price"] * Decimal(item["qty"])).quantize(Decimal("0.01"))
        commission = (item_total * item["rate"]).quantize(Decimal("0.01"))
        total_amount += item_total
        commission_total += commission

    assert total_amount == Decimal("38000.00")
    assert commission_total == Decimal("12500.00")


@pytest.mark.asyncio
async def test_create_order_empty_cart_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = OrderService(
        db=cast(DatabaseSessionProtocol, db),
        payment_provider=cast(PaymentProvider, _FakePaymentProvider()),
    )

    async def _fake_address(*, user_id: object, address_id: object) -> Mapping[str, object]:
        return _address_row()

    async def _fake_cart(*, user_id: object) -> list[Mapping[str, object]]:
        return []

    monkeypatch.setattr(service, "_get_user_address", _fake_address)
    monkeypatch.setattr(service, "_fetch_cart_with_brand_commission", _fake_cart)

    with pytest.raises(EmptyCartError):
        await service.create_order(
            user_id=uuid4(),
            address_id=uuid4(),
            delivery_provider="yandex_delivery",
            delivery_method="courier",
        )


@pytest.mark.asyncio
async def test_create_order_insufficient_stock_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeDb()
    service = OrderService(
        db=cast(DatabaseSessionProtocol, db),
        payment_provider=cast(PaymentProvider, _FakePaymentProvider()),
    )

    async def _fake_address(*, user_id: object, address_id: object) -> Mapping[str, object]:
        return _address_row()

    async def _fake_cart(*, user_id: object) -> list[Mapping[str, object]]:
        return [_cart_row(quantity=100, stock_quantity=5)]

    monkeypatch.setattr(service, "_get_user_address", _fake_address)
    monkeypatch.setattr(service, "_fetch_cart_with_brand_commission", _fake_cart)

    with pytest.raises(InsufficientStockError):
        await service.create_order(
            user_id=uuid4(),
            address_id=uuid4(),
            delivery_provider="yandex_delivery",
            delivery_method="courier",
        )


@pytest.mark.asyncio
async def test_create_order_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "frontend_base_url", "http://localhost:3000")
    db = _FakeDb()
    payment_provider = _FakePaymentProvider()
    delivery_provider = _FakeDeliveryProvider()
    service = OrderService(
        db=cast(DatabaseSessionProtocol, db),
        payment_provider=cast(PaymentProvider, payment_provider),
        delivery_provider=cast(DeliveryProvider, delivery_provider),
    )

    brand_id = uuid4()
    variant_id = uuid4()
    order_id = uuid4()
    order_item_id = uuid4()

    async def _fake_address(*, user_id: object, address_id: object) -> Mapping[str, object]:
        return _address_row()

    async def _fake_cart(*, user_id: object) -> list[Mapping[str, object]]:
        return [
            _cart_row(
                variant_id=variant_id,
                brand_id=brand_id,
                price_rub=Decimal("15000.00"),
                commission_rate=Decimal("0.3500"),
                quantity=1,
                stock_quantity=10,
            )
        ]

    async def _fake_validate(*, cart_rows: list[Mapping[str, object]]) -> None:
        return

    async def _fake_clear(*, user_id: object) -> None:
        return

    db.push_response([{"id": order_id}])
    db.push_response([{"id": order_item_id}])
    db.push_response([{"id": variant_id}])

    monkeypatch.setattr(service, "_get_user_address", _fake_address)
    monkeypatch.setattr(service, "_fetch_cart_with_brand_commission", _fake_cart)
    monkeypatch.setattr(service, "_validate_stock_for_cart", _fake_validate)
    monkeypatch.setattr(service, "_clear_cart", _fake_clear)

    result = await service.create_order(
        user_id=uuid4(),
        address_id=uuid4(),
        delivery_provider="yandex_delivery",
        delivery_method="courier",
    )

    assert result["id"] == order_id
    assert result["status"] == "pending"
    assert result["total_amount"] == Decimal("15000.00")
    assert result["customer_delivery_cost"] == Decimal("0.00")
    assert result["payment_url"] == "https://yookassa.ru/checkout/test"
    assert payment_provider.return_url == f"http://localhost:3000/order/success?id={order_id}"
    assert payment_provider.created is True
    assert delivery_provider.calculate_cost_called is False
    assert db.committed is True
    assert any(
        "INSERT INTO order_items" in statement and "RETURNING id" in statement
        for statement in db.statements
    )

    items = cast(list[Mapping[str, object]], result["items"])
    assert isinstance(items, list)
    assert len(items) == 1
    item = items[0]
    assert item["id"] == order_item_id
    assert item["product_variant_id"] == variant_id
    assert item["commission_rate"] == Decimal("0.3500")
    assert item["commission_amount"] == Decimal("5250.00")


@pytest.mark.asyncio
async def test_create_order_without_payment_provider_config_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))

    async def _fake_address(*, user_id: object, address_id: object) -> Mapping[str, object]:
        _ = user_id
        _ = address_id
        return _address_row()

    async def _fake_cart(*, user_id: object) -> list[Mapping[str, object]]:
        _ = user_id
        return [_cart_row(quantity=1, stock_quantity=10)]

    async def _fake_validate(*, cart_rows: list[Mapping[str, object]]) -> None:
        _ = cart_rows
        return

    async def _fake_clear(*, user_id: object) -> None:
        _ = user_id
        return

    monkeypatch.setattr(service, "_get_user_address", _fake_address)
    monkeypatch.setattr(service, "_fetch_cart_with_brand_commission", _fake_cart)
    monkeypatch.setattr(service, "_validate_stock_for_cart", _fake_validate)
    monkeypatch.setattr(service, "_clear_cart", _fake_clear)

    with pytest.raises(PaymentProviderNotConfiguredError):
        await service.create_order(
            user_id=uuid4(),
            address_id=uuid4(),
            delivery_provider="yandex_delivery",
            delivery_method="courier",
        )

    assert db.execute_calls == 0
    assert db.committed is False


@pytest.mark.asyncio
async def test_reserve_stock_raises_when_update_does_not_match_row() -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))

    with pytest.raises(InsufficientStockError):
        await service._reserve_stock(cart_rows=[_cart_row(quantity=1, stock_quantity=1)])


@pytest.mark.asyncio
async def test_create_sub_orders_links_items_to_brand_sub_orders() -> None:
    db = _FakeDb()
    delivery_provider = _FakeDeliveryProvider()
    service = OrderService(
        db=cast(DatabaseSessionProtocol, db),
        delivery_provider=cast(DeliveryProvider, delivery_provider),
    )

    order_id = uuid4()
    paid_at = datetime.now(UTC)
    brand_a = uuid4()
    brand_b = uuid4()
    variant_a = uuid4()
    variant_b = uuid4()
    sub_order_a = uuid4()
    sub_order_b = uuid4()

    db.push_response([])
    db.push_response(
        [
            {
                "id": uuid4(),
                "order_id": order_id,
                "sub_order_id": uuid4(),
                "brand_id": brand_a,
                "product_variant_id": variant_a,
                "quantity": 2,
                "unit_price": Decimal("1000.00"),
                "commission_rate": Decimal("0.3500"),
                "commission_amount": Decimal("700.00"),
                "vendor_code": "SKU-A",
                "size": "M",
                "color": None,
                "product_name": "Structured Jacket",
            },
            {
                "id": uuid4(),
                "order_id": order_id,
                "sub_order_id": uuid4(),
                "brand_id": brand_b,
                "product_variant_id": variant_b,
                "quantity": 1,
                "unit_price": Decimal("500.00"),
                "commission_rate": Decimal("0.2500"),
                "commission_amount": Decimal("125.00"),
                "vendor_code": "SKU-B",
                "size": "L",
                "color": None,
                "product_name": "Loose Shirt",
            },
        ]
    )
    db.push_response(
        [
            {
                "id": order_id,
                "delivery_address_json": {
                    "city": "Москва",
                    "street": "ул. Тверская, 1",
                    "apartment": "кв. 10",
                    "postal_code": "125009",
                },
            }
        ]
    )
    db.push_response([{"id": sub_order_a}])
    db.push_response([])
    db.push_response([{"id": sub_order_b}])
    db.push_response([])
    db.push_response(
        [
            _sub_order_row(
                order_id=order_id,
                brand_id=brand_a,
                sub_order_id=sub_order_a,
                status="paid",
                actual_delivery_cost=Decimal("500.00"),
                brand_name="MASLOV",
                items_count=1,
            ),
            _sub_order_row(
                order_id=order_id,
                brand_id=brand_b,
                sub_order_id=sub_order_b,
                status="paid",
                actual_delivery_cost=Decimal("500.00"),
                brand_name="LOOSE SHIRT",
                items_count=1,
            ),
        ]
    )

    result = await service.create_sub_orders(order_id=order_id, paid_at=paid_at)

    assert len(result) == 2
    assert {row["brand_id"] for row in result} == {brand_a, brand_b}
    update_params = [
        params
        for statement, params in zip(db.statements, db.execute_params, strict=False)
        if "UPDATE order_items" in statement
    ]
    assert any(
        params is not None and params["sub_order_id"] == sub_order_a for params in update_params
    )
    assert any(
        params is not None and params["sub_order_id"] == sub_order_b for params in update_params
    )
    insert_params = [
        params
        for statement, params in zip(db.statements, db.execute_params, strict=False)
        if "INSERT INTO sub_orders" in statement
    ]
    assert len(insert_params) == 2
    assert all(
        params is not None and params["actual_delivery_cost"] == Decimal("500.00")
        for params in insert_params
    )
    assert len(delivery_provider.calculate_cost_calls) == 2
    assert delivery_provider.calculate_cost_calls[0]["weight_kg"] == 1.0
    assert delivery_provider.calculate_cost_calls[0]["dimensions"] == {
        "length_cm": 30.0,
        "width_cm": 20.0,
        "height_cm": 10.0,
    }


@pytest.mark.asyncio
async def test_list_orders_includes_sub_orders() -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    order_id = uuid4()
    second_order_id = uuid4()
    brand_id = uuid4()
    second_brand_id = uuid4()
    created_at = datetime.now(UTC)

    db.push_response([{"cnt": 2}])
    db.push_response(
        [
            {
                "id": order_id,
                "status": "processing",
                "total_amount": Decimal("1500.00"),
                "customer_delivery_cost": Decimal("0.00"),
                "paid_at": None,
                "shipped_at": None,
                "delivered_at": None,
                "created_at": created_at,
                "items_count": 2,
            },
            {
                "id": second_order_id,
                "status": "paid",
                "total_amount": Decimal("2000.00"),
                "customer_delivery_cost": Decimal("0.00"),
                "paid_at": None,
                "shipped_at": None,
                "delivered_at": None,
                "created_at": created_at,
                "items_count": 1,
            },
        ]
    )
    db.push_response(
        [
            {
                **_sub_order_row(order_id=order_id, brand_id=brand_id, status="processing"),
                "brand_name": "MASLOV",
                "items_count": 1,
            },
            {
                **_sub_order_row(order_id=second_order_id, brand_id=second_brand_id),
                "brand_name": "SECOND",
                "items_count": 1,
            },
        ]
    )

    items, total = await service.list_orders(user_id=uuid4())

    assert total == 2
    assert db.execute_calls == 3
    assert not any(" o.tracking_number" in statement for statement in db.statements)
    sub_order_params = db.execute_params[2]
    assert sub_order_params is not None
    assert sub_order_params["order_ids"] == [order_id, second_order_id]
    assert items[0]["customer_delivery_cost"] == Decimal("0.00")
    assert "tracking_number" not in items[0]
    assert len(cast(list[Mapping[str, object]], items[0]["sub_orders"])) == 1
    sub_order = cast(list[Mapping[str, object]], items[0]["sub_orders"])[0]
    assert sub_order["brand_name"] == "MASLOV"
    assert sub_order["items_count"] == 1
    assert "brand_id" not in sub_order
    assert "order_id" not in sub_order
    assert sub_order["status"] == "processing"
    second_sub_order = cast(list[Mapping[str, object]], items[1]["sub_orders"])[0]
    assert second_sub_order["brand_name"] == "SECOND"


@pytest.mark.asyncio
async def test_get_order_detail_includes_sub_orders() -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    order_id = uuid4()
    user_id = uuid4()
    brand_id = uuid4()

    db.push_response(
        [
            {
                **_order_row(status="processing"),
                "id": order_id,
                "user_id": user_id,
                "customer_delivery_cost": Decimal("0.00"),
                "delivery_provider": "yandex_delivery",
                "delivery_method": "courier",
            }
        ]
    )
    db.push_response(
        [
            {
                "id": uuid4(),
                "order_id": order_id,
                "sub_order_id": uuid4(),
                "brand_id": uuid4(),
                "product_variant_id": uuid4(),
                "quantity": 1,
                "unit_price": Decimal("1000.00"),
                "commission_rate": Decimal("0.3500"),
                "commission_amount": Decimal("350.00"),
                "vendor_code": "SKU-1",
                "size": "M",
                "color": None,
                "product_name": "Item",
            }
        ]
    )
    db.push_response(
        [
            {
                **_sub_order_row(order_id=order_id, brand_id=brand_id, status="processing"),
                "brand_name": "MASLOV",
                "items_count": 1,
            }
        ]
    )

    payload = await service.get_order_detail(order_id=order_id, user_id=user_id)

    assert payload["status"] == "processing"
    assert payload["customer_delivery_cost"] == Decimal("0.00")
    assert not any(" o.tracking_number" in statement for statement in db.statements)
    assert "tracking_number" not in payload
    assert len(cast(list[Mapping[str, object]], payload["sub_orders"])) == 1
    sub_order = cast(list[Mapping[str, object]], payload["sub_orders"])[0]
    assert sub_order["brand_name"] == "MASLOV"
    assert sub_order["items_count"] == 1
    assert "brand_id" not in sub_order
    assert "order_id" not in sub_order


@pytest.mark.asyncio
async def test_create_refunds_links_refund_to_sub_order() -> None:
    db = _FakeDb()
    payment_provider = _FakePaymentProvider()
    service = OrderService(
        db=cast(DatabaseSessionProtocol, db),
        payment_provider=cast(PaymentProvider, payment_provider),
    )
    order_id = uuid4()
    sub_order_id = uuid4()
    item_id = uuid4()
    payment_id = uuid4()

    db.push_response(
        [
            {
                "id": item_id,
                "order_id": order_id,
                "sub_order_id": sub_order_id,
                "brand_id": uuid4(),
                "product_variant_id": uuid4(),
                "quantity": 2,
                "unit_price": Decimal("1000.00"),
                "commission_rate": Decimal("0.3500"),
                "commission_amount": Decimal("700.00"),
                "vendor_code": "SKU-1",
                "size": "M",
                "color": None,
                "product_name": "Item",
            }
        ]
    )
    db.push_response([])
    db.push_response(
        [
            {
                "id": payment_id,
                "external_payment_id": "pay-1",
                "status": "succeeded",
                "amount": Decimal("2000.00"),
            }
        ]
    )
    db.push_response([{"refunded_amount": Decimal("2000.00")}])
    db.push_response([])

    await service._create_refunds(order_id=order_id, from_status="paid", brand_id=None)

    refund_params = next(
        params
        for statement, params in zip(db.statements, db.execute_params, strict=False)
        if "INSERT INTO refunds" in statement
    )
    assert refund_params is not None
    assert refund_params["sub_order_id"] == sub_order_id
    assert refund_params["order_item_id"] == item_id


@pytest.mark.asyncio
async def test_create_refunds_keeps_payment_succeeded_after_partial_refund() -> None:
    db = _FakeDb()
    payment_provider = _FakePaymentProvider()
    service = OrderService(
        db=cast(DatabaseSessionProtocol, db),
        payment_provider=cast(PaymentProvider, payment_provider),
    )
    order_id = uuid4()
    payment_id = uuid4()

    db.push_response(
        [
            {
                "id": uuid4(),
                "order_id": order_id,
                "sub_order_id": uuid4(),
                "brand_id": uuid4(),
                "product_variant_id": uuid4(),
                "quantity": 1,
                "unit_price": Decimal("1000.00"),
                "commission_rate": Decimal("0.3500"),
                "commission_amount": Decimal("350.00"),
                "vendor_code": "SKU-1",
                "size": "M",
                "color": None,
                "product_name": "Item",
            }
        ]
    )
    db.push_response([])
    db.push_response(
        [
            {
                "id": payment_id,
                "external_payment_id": "pay-1",
                "status": "succeeded",
                "amount": Decimal("3000.00"),
            }
        ]
    )
    db.push_response([{"refunded_amount": Decimal("1000.00")}])

    await service._create_refunds(order_id=order_id, from_status="processing", brand_id=uuid4())

    assert payment_provider.refunds == [
        {
            "payment_id": "pay-1",
            "amount": Decimal("1000.00"),
            "reason": "Order cancellation",
        }
    ]
    assert not any("UPDATE payments" in statement for statement in db.statements)


@pytest.mark.asyncio
async def test_complete_sub_order_creates_payout_for_completed_sub_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb()
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    order_id = uuid4()
    sub_order_id = uuid4()
    brand_id = uuid4()
    delivered_at = datetime(2026, 2, 14, tzinfo=UTC)

    db.push_response([{"order_id": order_id}])
    db.push_response([{"value": "14"}])
    db.push_response(
        [
            {
                "sub_order_id": sub_order_id,
                "order_id": order_id,
                "brand_id": brand_id,
                "status": "completed",
                "items_total": Decimal("1000.00"),
                "delivered_at": delivered_at,
                "brand_name": "MASLOV",
                "commission_total": Decimal("350.00"),
            }
        ]
    )
    db.push_response([])
    db.push_response([])
    db.push_response(
        [
            _sub_order_row(
                order_id=order_id,
                brand_id=brand_id,
                sub_order_id=sub_order_id,
                status="completed",
            )
        ]
    )
    db.push_response([_order_row(status="delivered") | {"id": order_id}])
    db.push_response([])
    db.push_response([_order_row(status="completed") | {"id": order_id}])

    async def _fake_notify(
        *,
        order: Mapping[str, object],
        status: str,
        tracking_number: str | None = None,
    ) -> None:
        _ = order
        _ = status
        _ = tracking_number
        return

    monkeypatch.setattr(service, "_notify_buyer_status_change", _fake_notify)

    result = await service.complete_sub_order(
        sub_order_id=sub_order_id,
        completed_at=delivered_at,
    )

    assert result["sub_order_id"] == sub_order_id
    assert result["status"] == "completed"
    payout_params = next(
        params
        for statement, params in zip(db.statements, db.execute_params, strict=False)
        if "INSERT INTO payouts" in statement
    )
    assert payout_params is not None
    assert payout_params["sub_order_id"] == sub_order_id
    assert payout_params["brand_id"] == brand_id
    assert payout_params["amount"] == Decimal("650.00")
    assert payout_params["scheduled_at"] == datetime(2026, 3, 1, tzinfo=UTC)
