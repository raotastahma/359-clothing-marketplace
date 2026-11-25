from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol, cast, runtime_checkable
from uuid import UUID

import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable

from app.core.config import settings
from app.integrations.delivery import get_delivery_provider
from app.integrations.delivery.protocol import DeliveryProvider
from app.integrations.payments import get_payment_provider
from app.integrations.payments.protocol import PaymentProvider
from app.services.notification_service import NotificationService
from app.services.payout_service import PayoutService

ORDER_STATUSES = frozenset(
    {
        "pending",
        "paid",
        "processing",
        "shipped",
        "delivered",
        "completed",
        "cancelled_by_buyer",
        "cancelled_by_brand",
        "returned",
    }
)
TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"paid", "cancelled_by_buyer"}),
    "paid": frozenset({"processing", "cancelled_by_buyer", "cancelled_by_brand"}),
    "processing": frozenset({"shipped", "cancelled_by_brand"}),
    "shipped": frozenset({"delivered"}),
    "delivered": frozenset({"completed", "returned"}),
}
SUB_ORDER_TRANSITIONS: dict[str, frozenset[str]] = {
    "paid": frozenset({"processing", "cancelled_by_brand"}),
    "processing": frozenset({"shipped", "cancelled_by_brand"}),
    "shipped": frozenset({"delivered"}),
    "delivered": frozenset({"completed", "returned"}),
}

SUB_ORDER_DELIVERY_WEIGHT_KG = 1.0
SUB_ORDER_DELIVERY_DIMENSIONS: dict[str, float] = {
    "length_cm": 30.0,
    "width_cm": 20.0,
    "height_cm": 10.0,
}


@dataclass(frozen=True, slots=True)
class InvalidTransitionError(ValueError):
    current_status: str
    target_status: str

    @property
    def message(self) -> str:
        return f"Cannot change order status from {self.current_status} to {self.target_status}"


class OrderNotFoundError(ValueError):
    pass


class InsufficientStockError(ValueError):
    pass


class EmptyCartError(ValueError):
    pass


class AddressNotFoundError(ValueError):
    pass


class PaymentProviderNotConfiguredError(ValueError):
    pass


@runtime_checkable
class MappingResultProtocol(Protocol):
    def first(self) -> Mapping[str, object] | None: ...

    def all(self) -> list[Mapping[str, object]]: ...


@runtime_checkable
class ExecuteResultProtocol(Protocol):
    def mappings(self) -> MappingResultProtocol: ...

    def scalar_one_or_none(self) -> object: ...


@runtime_checkable
class DatabaseSessionProtocol(Protocol):
    async def execute(
        self,
        statement: Executable,
        params: Mapping[str, object] | None = None,
    ) -> ExecuteResultProtocol: ...

    async def commit(self) -> None: ...


@beartype
def _to_uuid(value: object) -> UUID:
    return UUID(str(value))


@beartype
def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError("Expected integer-compatible value.")


@beartype
def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float, str)):
        return Decimal(str(value))
    raise TypeError("Expected decimal-compatible value.")


@beartype
def _sub_order_summary_from_row(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "id": _to_uuid(row["id"]),
        "brand_name": str(row["brand_name"]),
        "status": str(row["status"]),
        "tracking_number": cast(str | None, row["tracking_number"]),
        "items_count": _to_int(row["items_count"]),
    }


class OrderService:
    @beartype
    def __init__(
        self,
        *,
        db: DatabaseSessionProtocol,
        payment_provider: PaymentProvider | None = None,
        delivery_provider: DeliveryProvider | None = None,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._db = db
        self._payment_provider = payment_provider
        self._payment_provider_error: PaymentProviderNotConfiguredError | None = None
        if self._payment_provider is None:
            try:
                self._payment_provider = get_payment_provider()
            except ValueError:
                self._payment_provider = None
                self._payment_provider_error = PaymentProviderNotConfiguredError(
                    "Payment provider is not configured."
                )
        self._delivery_provider = delivery_provider or get_delivery_provider()
        self._notification_service = notification_service or NotificationService()

    # ------------------------------------------------------------------
    # Create order from cart
    # ------------------------------------------------------------------

    @beartype
    async def create_order(
        self,
        *,
        user_id: UUID,
        address_id: UUID,
        delivery_provider: str,
        delivery_method: str,
        comment: str | None = None,
    ) -> dict[str, object]:
        address = await self._get_user_address(user_id=user_id, address_id=address_id)
        cart_rows = await self._fetch_cart_with_brand_commission(user_id=user_id)
        if not cart_rows:
            raise EmptyCartError("Cart is empty.")

        await self._validate_stock_for_cart(cart_rows=cart_rows)
        payment_provider = self._require_payment_provider()

        total_amount = Decimal("0.00")
        commission_total = Decimal("0.00")
        items_data: list[dict[str, object]] = []
        created_item_ids: list[UUID] = []

        for row in cart_rows:
            quantity = _to_int(row["quantity"])
            unit_price = _to_decimal(row["price_rub"])
            commission_rate = _to_decimal(row["commission_rate"])
            item_total = (unit_price * Decimal(quantity)).quantize(Decimal("0.01"))
            commission_amount = (item_total * commission_rate).quantize(Decimal("0.01"))
            total_amount += item_total
            commission_total += commission_amount
            items_data.append(
                {
                    "product_variant_id": _to_uuid(row["variant_id"]),
                    "brand_id": _to_uuid(row["brand_id"]),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "commission_rate": commission_rate,
                    "commission_amount": commission_amount,
                    "product_name": str(row["product_name"]),
                    "vendor_code": cast(str | None, row.get("vendor_code")),
                    "size": str(row["size"]),
                    "color": cast(str | None, row.get("color")),
                }
            )

        delivery_address_json = {
            "city": str(address.get("city", "")),
            "street": str(address.get("street", "")),
            "apartment": cast(str | None, address.get("apartment")),
            "postal_code": cast(str | None, address.get("postal_code")),
        }
        customer_delivery_cost = Decimal("0.00")

        result = await self._db.execute(
            sa.text(
                """
                INSERT INTO orders (
                    user_id, status, total_amount, commission_total,
                    delivery_provider, delivery_method, customer_delivery_cost,
                    delivery_address_json
                )
                VALUES (
                    :user_id, 'pending', :total_amount, :commission_total,
                    :delivery_provider, :delivery_method, :customer_delivery_cost,
                    CAST(:delivery_address_json AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "user_id": user_id,
                "total_amount": total_amount.quantize(Decimal("0.01")),
                "commission_total": commission_total.quantize(Decimal("0.01")),
                "delivery_provider": delivery_provider,
                "delivery_method": delivery_method,
                "customer_delivery_cost": customer_delivery_cost,
                "delivery_address_json": json.dumps(delivery_address_json, ensure_ascii=False),
            },
        )
        order_row = result.mappings().first()
        if order_row is None:
            raise ValueError("Failed to create order.")
        order_id = _to_uuid(order_row["id"])

        for item in items_data:
            result = await self._db.execute(
                sa.text(
                    """
                    INSERT INTO order_items (
                        order_id, product_variant_id, brand_id,
                        quantity, unit_price, commission_rate, commission_amount
                    )
                    VALUES (
                        :order_id, :product_variant_id, :brand_id,
                        :quantity, :unit_price, :commission_rate, :commission_amount
                    )
                    RETURNING id
                    """
                ),
                {
                    "order_id": order_id,
                    "product_variant_id": item["product_variant_id"],
                    "brand_id": item["brand_id"],
                    "quantity": item["quantity"],
                    "unit_price": item["unit_price"],
                    "commission_rate": item["commission_rate"],
                    "commission_amount": item["commission_amount"],
                },
            )
            item_row = result.mappings().first()
            if item_row is None:
                raise ValueError("Failed to create order item.")
            created_item_ids.append(_to_uuid(item_row["id"]))

        await self._reserve_stock(cart_rows=cart_rows)
        await self._clear_cart(user_id=user_id)

        return_url = f"{settings.frontend_base_url.rstrip('/')}/order/success?id={order_id}"
        payment_result = await payment_provider.create_payment(
            amount=total_amount,
            order_id=order_id,
            return_url=return_url,
            description=f"Заказ 359 Marketplace #{str(order_id)[:8].upper()}",
        )
        await self._db.execute(
            sa.text(
                """
                INSERT INTO payments (order_id, provider, external_payment_id, status, amount)
                VALUES (:order_id, 'yookassa', :external_payment_id, 'pending', :amount)
                """
            ),
            {
                "order_id": order_id,
                "external_payment_id": payment_result.external_payment_id,
                "amount": total_amount,
            },
        )
        payment_url = payment_result.payment_url

        await self._db.commit()

        order_items_payload = [
            {
                "id": item_id,
                "product_variant_id": item["product_variant_id"],
                "brand_id": item["brand_id"],
                "product_name": item["product_name"],
                "vendor_code": item["vendor_code"],
                "size": item["size"],
                "color": item["color"],
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
                "commission_rate": item["commission_rate"],
                "commission_amount": item["commission_amount"],
            }
            for item, item_id in zip(items_data, created_item_ids, strict=True)
        ]

        return {
            "id": order_id,
            "status": "pending",
            "total_amount": total_amount.quantize(Decimal("0.01")),
            "customer_delivery_cost": customer_delivery_cost,
            "items": order_items_payload,
            "payment_url": payment_url,
        }

    @beartype
    def _require_payment_provider(self) -> PaymentProvider:
        if self._payment_provider is not None:
            return self._payment_provider
        if self._payment_provider_error is not None:
            raise self._payment_provider_error
        raise PaymentProviderNotConfiguredError("Payment provider is not configured.")

    # ------------------------------------------------------------------
    # List user orders
    # ------------------------------------------------------------------

    @beartype
    async def list_orders(
        self,
        *,
        user_id: UUID,
        page: int = 1,
        per_page: int = 10,
        status_filter: str | None = None,
    ) -> tuple[list[dict[str, object]], int]:
        where_parts = ["o.user_id = :user_id"]
        params: dict[str, object] = {"user_id": user_id}

        if status_filter is not None:
            where_parts.append("o.status = :status_filter")
            params["status_filter"] = status_filter

        where_clause = " AND ".join(where_parts)
        count_result = await self._db.execute(
            sa.text(f"SELECT COUNT(*) AS cnt FROM orders o WHERE {where_clause}"),
            params,
        )
        count_row = count_result.mappings().first()
        total = _to_int(count_row["cnt"]) if count_row else 0

        offset = (page - 1) * per_page
        params["limit"] = per_page
        params["offset"] = offset

        result = await self._db.execute(
            sa.text(
                f"""
                SELECT
                    o.id,
                    o.status,
                    o.total_amount,
                    o.customer_delivery_cost,
                    o.paid_at,
                    o.shipped_at,
                    o.delivered_at,
                    o.created_at,
                    (SELECT COUNT(*)::int FROM order_items oi WHERE oi.order_id = o.id) AS items_count
                FROM orders o
                WHERE {where_clause}
                ORDER BY o.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        order_rows = result.mappings().all()
        order_ids = [_to_uuid(row["id"]) for row in order_rows]
        sub_orders_by_order_id: dict[UUID, list[dict[str, object]]] = {
            order_id: [] for order_id in order_ids
        }
        sub_order_rows = await self._fetch_sub_order_rows_for_orders(order_ids=order_ids)
        for sub_order_row in sub_order_rows:
            sub_order_order_id = _to_uuid(sub_order_row["order_id"])
            if sub_order_order_id in sub_orders_by_order_id:
                sub_orders_by_order_id[sub_order_order_id].append(
                    _sub_order_summary_from_row(sub_order_row)
                )

        orders: list[dict[str, object]] = []
        for row, order_id in zip(order_rows, order_ids, strict=True):
            orders.append(
                {
                    "id": order_id,
                    "status": str(row["status"]),
                    "total_amount": _to_decimal(row["total_amount"]),
                    "customer_delivery_cost": _to_decimal(row["customer_delivery_cost"]),
                    "items_count": _to_int(row["items_count"]),
                    "sub_orders": sub_orders_by_order_id[order_id],
                    "paid_at": cast(datetime | None, row["paid_at"]),
                    "shipped_at": cast(datetime | None, row["shipped_at"]),
                    "delivered_at": cast(datetime | None, row["delivered_at"]),
                    "created_at": cast(datetime, row["created_at"]),
                }
            )
        return orders, total

    # ------------------------------------------------------------------
    # Get order detail
    # ------------------------------------------------------------------

    @beartype
    async def get_order_detail(
        self,
        *,
        order_id: UUID,
        user_id: UUID,
    ) -> dict[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    o.id, o.user_id, o.status, o.total_amount, o.commission_total,
                    o.customer_delivery_cost, o.delivery_provider, o.delivery_method,
                    o.delivery_address_json,
                    o.paid_at, o.shipped_at, o.delivered_at, o.created_at
                FROM orders o
                WHERE o.id = :order_id
                LIMIT 1
                """
            ),
            {"order_id": order_id},
        )
        order = result.mappings().first()
        if order is None:
            raise OrderNotFoundError("Order not found.")
        if _to_uuid(order["user_id"]) != user_id:
            raise OrderNotFoundError("Order not found.")

        items = await self.list_order_items(order_id=order_id)
        sub_orders = await self.list_sub_orders(order_id=order_id)
        items_payload = [
            {
                "id": _to_uuid(item["id"]),
                "product_variant_id": _to_uuid(item["product_variant_id"]),
                "brand_id": _to_uuid(item["brand_id"]),
                "product_name": str(item["product_name"]),
                "vendor_code": cast(str | None, item.get("vendor_code")),
                "size": str(item["size"]),
                "color": cast(str | None, item.get("color")),
                "quantity": _to_int(item["quantity"]),
                "unit_price": _to_decimal(item["unit_price"]),
                "commission_rate": _to_decimal(item["commission_rate"]),
                "commission_amount": _to_decimal(item["commission_amount"]),
            }
            for item in items
        ]

        delivery_provider_raw = order["delivery_provider"]
        return {
            "id": _to_uuid(order["id"]),
            "status": str(order["status"]),
            "total_amount": _to_decimal(order["total_amount"]),
            "commission_total": _to_decimal(order["commission_total"]),
            "customer_delivery_cost": _to_decimal(order["customer_delivery_cost"]),
            "delivery_provider": str(delivery_provider_raw) if delivery_provider_raw else None,
            "delivery_method": cast(str | None, order["delivery_method"]),
            "delivery_address": cast(dict[str, object] | None, order["delivery_address_json"]),
            "items": items_payload,
            "sub_orders": sub_orders,
            "paid_at": cast(datetime | None, order["paid_at"]),
            "shipped_at": cast(datetime | None, order["shipped_at"]),
            "delivered_at": cast(datetime | None, order["delivered_at"]),
            "created_at": cast(datetime, order["created_at"]),
        }

    # ------------------------------------------------------------------
    # Cancel by buyer
    # ------------------------------------------------------------------

    @beartype
    async def cancel_by_buyer(self, *, order_id: UUID, user_id: UUID) -> dict[str, object]:
        order = await self._get_order_snapshot(order_id=order_id)
        if _to_uuid(order["user_id"]) != user_id:
            raise OrderNotFoundError("Order not found.")
        return await self.transition_order(
            order_id=order_id,
            target_status="cancelled_by_buyer",
        )

    @beartype
    async def transition_order(
        self,
        *,
        order_id: UUID,
        target_status: str,
        brand_id: UUID | None = None,
        notify_buyer: bool = True,
        commit: bool = True,
    ) -> dict[str, object]:
        if target_status not in ORDER_STATUSES:
            raise ValueError(f"Unknown order status: {target_status}")

        order = await self._get_order_snapshot(order_id=order_id)
        current_status = str(order["status"])
        if current_status == target_status:
            return self._status_payload_from_order(order=order)
        self._validate_transition(current_status=current_status, target_status=target_status)

        now_utc = datetime.now(UTC)
        if target_status in {"cancelled_by_buyer", "cancelled_by_brand"}:
            await self._release_stock(order_id=order_id, brand_id=brand_id)
            if current_status in {"paid", "processing"}:
                await self._create_refunds(
                    order_id=order_id,
                    from_status=current_status,
                    brand_id=brand_id,
                )

        update_parts: list[str] = ["status = :target_status"]
        params: dict[str, object] = {"order_id": order_id, "target_status": target_status}
        if target_status == "paid":
            update_parts.append("paid_at = COALESCE(paid_at, :paid_at)")
            params["paid_at"] = now_utc
        if target_status == "shipped":
            update_parts.append("shipped_at = COALESCE(shipped_at, :shipped_at)")
            params["shipped_at"] = now_utc
        if target_status == "delivered":
            update_parts.append("delivered_at = COALESCE(delivered_at, :delivered_at)")
            params["delivered_at"] = now_utc

        await self._db.execute(
            sa.text(
                f"""
                UPDATE orders
                SET {", ".join(update_parts)}
                WHERE id = :order_id
                """
            ),
            params,
        )
        if commit:
            await self._db.commit()

        updated_order = await self._get_order_snapshot(order_id=order_id)
        if notify_buyer:
            await self._notify_buyer_status_change(order=updated_order, status=target_status)
        return self._status_payload_from_order(order=updated_order)

    @beartype
    async def list_order_items(
        self,
        *,
        order_id: UUID,
        brand_id: UUID | None = None,
    ) -> list[dict[str, object]]:
        where_brand = "AND oi.brand_id = :brand_id" if brand_id is not None else ""
        result = await self._db.execute(
            sa.text(
                f"""
                SELECT
                    oi.id,
                    oi.order_id,
                    oi.sub_order_id,
                    oi.brand_id,
                    oi.product_variant_id,
                    oi.quantity,
                    oi.unit_price,
                    oi.commission_rate,
                    oi.commission_amount,
                    pv.vendor_code,
                    pv.size,
                    pv.color,
                    p.name AS product_name
                FROM order_items oi
                JOIN product_variants pv ON pv.id = oi.product_variant_id
                JOIN products p ON p.id = pv.product_id
                WHERE oi.order_id = :order_id
                {where_brand}
                ORDER BY oi.id ASC
                """
            ),
            {"order_id": order_id, "brand_id": brand_id},
        )
        return [dict(row) for row in result.mappings().all()]

    @beartype
    async def _fetch_sub_order_rows(self, *, order_id: UUID) -> list[Mapping[str, object]]:
        return await self._fetch_sub_order_rows_for_orders(order_ids=[order_id])

    @beartype
    async def _fetch_sub_order_rows_for_orders(
        self, *, order_ids: Sequence[UUID]
    ) -> list[Mapping[str, object]]:
        if not order_ids:
            return []

        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    so.id,
                    so.order_id,
                    so.brand_id,
                    b.name AS brand_name,
                    so.status,
                    so.items_total,
                    so.commission_total,
                    so.actual_delivery_cost,
                    so.tracking_number,
                    so.confirmation_deadline,
                    so.shipping_deadline,
                    so.confirmed_at,
                    so.shipped_at,
                    so.delivered_at,
                    so.completed_at,
                    so.created_at,
                    (
                        SELECT COUNT(*)::int
                        FROM order_items oi
                        WHERE oi.sub_order_id = so.id
                    ) AS items_count
                FROM sub_orders so
                JOIN brands b ON b.id = so.brand_id
                WHERE so.order_id IN :order_ids
                ORDER BY so.order_id ASC, so.created_at ASC, so.id ASC
                """
            ).bindparams(sa.bindparam("order_ids", expanding=True)),
            {"order_ids": list(order_ids)},
        )
        return result.mappings().all()

    @beartype
    async def list_sub_orders(self, *, order_id: UUID) -> list[dict[str, object]]:
        rows = await self._fetch_sub_order_rows(order_id=order_id)
        return [_sub_order_summary_from_row(row) for row in rows]

    @beartype
    async def complete_sub_order(
        self,
        *,
        sub_order_id: UUID,
        completed_at: datetime | None = None,
        commit: bool = True,
    ) -> dict[str, object]:
        now_utc = completed_at or datetime.now(UTC)
        result = await self._db.execute(
            sa.text(
                """
                UPDATE sub_orders
                SET status = 'completed',
                    delivered_at = COALESCE(delivered_at, :completed_at),
                    completed_at = COALESCE(completed_at, :completed_at)
                WHERE id = :sub_order_id
                  AND status = 'delivered'
                RETURNING order_id
                """
            ),
            {"sub_order_id": sub_order_id, "completed_at": now_utc},
        )
        row = result.mappings().first()
        if row is None:
            raise OrderNotFoundError("Sub-order not found or cannot be completed.")

        payout_service = PayoutService(db=self._db)
        await payout_service.create_payout_for_sub_order(sub_order_id=sub_order_id)
        await self.sync_order_status_from_sub_orders(
            order_id=_to_uuid(row["order_id"]), commit=False
        )

        if commit:
            await self._db.commit()

        return {
            "order_id": _to_uuid(row["order_id"]),
            "sub_order_id": sub_order_id,
            "status": "completed",
        }

    @beartype
    async def handle_sub_order_cancelled_by_brand(
        self,
        *,
        order_id: UUID,
        brand_id: UUID,
        refund_from_status: str | None = None,
        commit: bool = True,
    ) -> dict[str, object]:
        order = await self._get_order_snapshot(order_id=order_id)
        current_status = refund_from_status or str(order["status"])
        await self._release_stock(order_id=order_id, brand_id=brand_id)
        if current_status in {"paid", "processing"}:
            await self._create_refunds(
                order_id=order_id,
                from_status=current_status,
                brand_id=brand_id,
            )
        return await self.sync_order_status_from_sub_orders(order_id=order_id, commit=commit)

    @beartype
    async def sync_order_status_from_sub_orders(
        self,
        *,
        order_id: UUID,
        tracking_number: str | None = None,
        notify_buyer: bool = True,
        commit: bool = True,
    ) -> dict[str, object]:
        rows = await self._fetch_sub_order_rows(order_id=order_id)
        target_status = self._aggregate_order_status_from_sub_orders(
            statuses=[str(row["status"]) for row in rows]
        )
        order = await self._get_order_snapshot(order_id=order_id)
        if target_status is None:
            return self._status_payload_from_order(order=order)
        if str(order["status"]) == target_status:
            if notify_buyer and target_status == "shipped" and tracking_number:
                await self._notify_buyer_status_change(
                    order=order,
                    status=target_status,
                    tracking_number=tracking_number,
                )
            return self._status_payload_from_order(order=order)

        now_utc = datetime.now(UTC)
        update_parts = ["status = :target_status"]
        params: dict[str, object] = {"order_id": order_id, "target_status": target_status}
        if target_status == "shipped":
            update_parts.append("shipped_at = COALESCE(shipped_at, :changed_at)")
            params["changed_at"] = now_utc
        elif target_status == "delivered":
            update_parts.append("delivered_at = COALESCE(delivered_at, :changed_at)")
            params["changed_at"] = now_utc

        await self._db.execute(
            sa.text(
                f"""
                UPDATE orders
                SET {", ".join(update_parts)}
                WHERE id = :order_id
                """
            ),
            params,
        )
        if commit:
            await self._db.commit()

        updated_order = await self._get_order_snapshot(order_id=order_id)
        if notify_buyer:
            await self._notify_buyer_status_change(
                order=updated_order,
                status=target_status,
                tracking_number=tracking_number,
            )
        return self._status_payload_from_order(order=updated_order)

    @beartype
    def _aggregate_order_status_from_sub_orders(self, *, statuses: list[str]) -> str | None:
        if not statuses:
            return None
        if all(status == "completed" for status in statuses):
            return "completed"
        if all(status in {"delivered", "completed"} for status in statuses):
            return "delivered"
        if any(status in {"shipped", "delivered", "completed"} for status in statuses):
            return "shipped"
        if all(status in {"paid", "processing"} for status in statuses):
            return "paid"
        if all(status == "cancelled_by_brand" for status in statuses):
            return "cancelled_by_brand"
        return None

    @beartype
    def _sub_order_internal_payload(self, row: Mapping[str, object]) -> dict[str, object]:
        return {
            "id": _to_uuid(row["id"]),
            "order_id": _to_uuid(row["order_id"]),
            "brand_id": _to_uuid(row["brand_id"]),
            "brand_name": str(row["brand_name"]),
            "status": str(row["status"]),
            "items_total": _to_decimal(row["items_total"]),
            "commission_total": _to_decimal(row["commission_total"]),
            "actual_delivery_cost": _to_decimal(row["actual_delivery_cost"]),
            "tracking_number": cast(str | None, row["tracking_number"]),
            "confirmation_deadline": cast(datetime | None, row["confirmation_deadline"]),
            "shipping_deadline": cast(datetime | None, row["shipping_deadline"]),
            "confirmed_at": cast(datetime | None, row["confirmed_at"]),
            "shipped_at": cast(datetime | None, row["shipped_at"]),
            "delivered_at": cast(datetime | None, row["delivered_at"]),
            "completed_at": cast(datetime | None, row["completed_at"]),
            "created_at": cast(datetime, row["created_at"]),
            "items_count": _to_int(row["items_count"]),
        }

    @beartype
    async def create_sub_orders(
        self,
        *,
        order_id: UUID,
        paid_at: datetime,
    ) -> list[dict[str, object]]:
        existing_rows = await self._fetch_sub_order_rows(order_id=order_id)
        if existing_rows:
            await self._bind_order_items_to_sub_orders(order_id=order_id)
            refreshed_rows = await self._fetch_sub_order_rows(order_id=order_id)
            return [self._sub_order_internal_payload(row) for row in refreshed_rows]

        items = await self.list_order_items(order_id=order_id)
        if not items:
            raise ValueError("Order has no items to split into sub_orders.")
        order = await self._get_order_snapshot(order_id=order_id)
        delivery_address = self._delivery_address_for_cost(
            delivery_address_json=order.get("delivery_address_json")
        )

        grouped_items: dict[UUID, list[Mapping[str, object]]] = {}
        brand_order: list[UUID] = []
        for item in items:
            brand_id = _to_uuid(item["brand_id"])
            if brand_id not in grouped_items:
                grouped_items[brand_id] = []
                brand_order.append(brand_id)
            grouped_items[brand_id].append(item)

        confirmation_deadline = paid_at + timedelta(hours=24)
        shipping_deadline = paid_at + timedelta(hours=48)

        for brand_id in brand_order:
            brand_items = grouped_items[brand_id]
            items_total = Decimal("0.00")
            commission_total = Decimal("0.00")
            for brand_item in brand_items:
                quantity = _to_int(brand_item["quantity"])
                unit_price = _to_decimal(brand_item["unit_price"])
                commission_amount = _to_decimal(brand_item["commission_amount"])
                items_total += (unit_price * Decimal(quantity)).quantize(Decimal("0.01"))
                commission_total += commission_amount.quantize(Decimal("0.01"))

            delivery_estimate = await self._delivery_provider.calculate_cost(
                address=delivery_address,
                weight_kg=SUB_ORDER_DELIVERY_WEIGHT_KG,
                dimensions=dict(SUB_ORDER_DELIVERY_DIMENSIONS),
            )

            result = await self._db.execute(
                sa.text(
                    """
                    INSERT INTO sub_orders (
                        order_id,
                        brand_id,
                        status,
                        items_total,
                        commission_total,
                        actual_delivery_cost,
                        confirmation_deadline,
                        shipping_deadline
                    )
                    VALUES (
                        :order_id,
                        :brand_id,
                        'paid',
                        :items_total,
                        :commission_total,
                        :actual_delivery_cost,
                        :confirmation_deadline,
                        :shipping_deadline
                    )
                    RETURNING id
                    """
                ),
                {
                    "order_id": order_id,
                    "brand_id": brand_id,
                    "items_total": items_total.quantize(Decimal("0.01")),
                    "commission_total": commission_total.quantize(Decimal("0.01")),
                    "actual_delivery_cost": delivery_estimate.cost.quantize(Decimal("0.01")),
                    "confirmation_deadline": confirmation_deadline,
                    "shipping_deadline": shipping_deadline,
                },
            )
            row = result.mappings().first()
            if row is None:
                raise ValueError("Failed to create sub_order.")
            sub_order_id = _to_uuid(row["id"])

            await self._db.execute(
                sa.text(
                    """
                    UPDATE order_items
                    SET sub_order_id = :sub_order_id
                    WHERE order_id = :order_id
                      AND brand_id = :brand_id
                    """
                ),
                {
                    "order_id": order_id,
                    "brand_id": brand_id,
                    "sub_order_id": sub_order_id,
                },
            )

        created_rows = await self._fetch_sub_order_rows(order_id=order_id)
        return [self._sub_order_internal_payload(row) for row in created_rows]

    @beartype
    async def _bind_order_items_to_sub_orders(self, *, order_id: UUID) -> None:
        await self._db.execute(
            sa.text(
                """
                UPDATE order_items oi
                SET sub_order_id = so.id
                FROM sub_orders so
                WHERE oi.order_id = :order_id
                  AND so.order_id = :order_id
                  AND oi.brand_id = so.brand_id
                """
            ),
            {"order_id": order_id},
        )

    @beartype
    async def get_order_payload_for_notifications(self, *, order_id: UUID) -> dict[str, object]:
        order = await self._get_order_snapshot(order_id=order_id)
        return {
            "id": _to_uuid(order["id"]),
            "number": f"ORD-{str(order['id'])[:8].upper()}",
            "created_at": cast(datetime, order["created_at"]),
            "buyer_full_name": cast(str | None, order["buyer_name"]) or "Customer",
            "buyer_phone": str(order["buyer_phone"]),
            "buyer_email": cast(str | None, order["buyer_email"]),
            "delivery_address": self._format_delivery_address(order.get("delivery_address_json")),
        }

    @beartype
    async def get_brand_notification_emails(self, *, order_id: UUID) -> dict[UUID, list[str]]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT DISTINCT b.id AS brand_id, b.notification_emails
                FROM order_items oi
                JOIN brands b ON b.id = oi.brand_id
                WHERE oi.order_id = :order_id
                """
            ),
            {"order_id": order_id},
        )
        payload: dict[UUID, list[str]] = {}
        for row in result.mappings().all():
            brand_id = _to_uuid(row["brand_id"])
            raw_emails = row["notification_emails"]
            if isinstance(raw_emails, list):
                typed_emails = cast(list[object], raw_emails)
                payload[brand_id] = [str(item) for item in typed_emails if str(item)]
            else:
                payload[brand_id] = []
        return payload

    @beartype
    async def _get_order_snapshot(self, *, order_id: UUID) -> Mapping[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    o.id,
                    o.user_id,
                    o.status,
                    o.total_amount,
                    o.commission_total,
                    o.customer_delivery_cost,
                    o.paid_at,
                    o.shipped_at,
                    o.delivered_at,
                    o.created_at,
                    o.delivery_address_json,
                    u.email AS buyer_email,
                    u.name AS buyer_name,
                    u.phone AS buyer_phone
                FROM orders o
                JOIN users u ON u.id = o.user_id
                WHERE o.id = :order_id
                LIMIT 1
                """
            ),
            {"order_id": order_id},
        )
        row = result.mappings().first()
        if row is None:
            raise OrderNotFoundError("Order not found.")
        return row

    @beartype
    def _validate_transition(self, *, current_status: str, target_status: str) -> None:
        allowed = TRANSITIONS.get(current_status, frozenset())
        if target_status not in allowed:
            raise InvalidTransitionError(
                current_status=current_status,
                target_status=target_status,
            )

    @beartype
    async def _release_stock(self, *, order_id: UUID, brand_id: UUID | None) -> None:
        where_brand = "AND oi.brand_id = :brand_id" if brand_id is not None else ""
        await self._db.execute(
            sa.text(
                f"""
                UPDATE product_variants pv
                SET stock_quantity = pv.stock_quantity + x.quantity
                FROM (
                    SELECT oi.product_variant_id, SUM(oi.quantity)::int AS quantity
                    FROM order_items oi
                    WHERE oi.order_id = :order_id
                    {where_brand}
                    GROUP BY oi.product_variant_id
                ) AS x
                WHERE pv.id = x.product_variant_id
                """
            ),
            {"order_id": order_id, "brand_id": brand_id},
        )

    @beartype
    async def _create_refunds(
        self,
        *,
        order_id: UUID,
        from_status: str,
        brand_id: UUID | None,
    ) -> None:
        items = await self.list_order_items(order_id=order_id, brand_id=brand_id)
        if not items:
            return

        refund_total = Decimal("0.00")
        for item in items:
            quantity = _to_int(item["quantity"])
            unit_price = _to_decimal(item["unit_price"])
            item_total = (unit_price * Decimal(quantity)).quantize(Decimal("0.01"))
            commission_refund = _to_decimal(item["commission_amount"]).quantize(Decimal("0.01"))
            refund_total += item_total
            await self._db.execute(
                sa.text(
                    """
                    INSERT INTO refunds (
                        order_id,
                        sub_order_id,
                        order_item_id,
                        amount,
                        commission_refund,
                        reason,
                        status
                    )
                    VALUES (
                        :order_id,
                        :sub_order_id,
                        :order_item_id,
                        :amount,
                        :commission_refund,
                        :reason,
                        'pending'
                    )
                    """
                ),
                {
                    "order_id": order_id,
                    "sub_order_id": (
                        _to_uuid(item["sub_order_id"]) if item.get("sub_order_id") else None
                    ),
                    "order_item_id": _to_uuid(item["id"]),
                    "amount": item_total,
                    "commission_refund": commission_refund,
                    "reason": f"Order status changed from {from_status} to cancellation.",
                },
            )

        payment_row = await self._get_latest_payment(order_id=order_id)
        if payment_row is None:
            return
        payment_id = cast(str | None, payment_row["external_payment_id"])
        payment_status = str(payment_row["status"])
        if payment_id and payment_status in {"succeeded", "waiting_for_capture"}:
            if self._payment_provider is not None:
                await self._payment_provider.create_refund(
                    payment_id=payment_id,
                    amount=refund_total.quantize(Decimal("0.01")),
                    reason="Order cancellation",
                )
            refunded_amount = await self._get_order_refund_total(order_id=order_id)
            payment_amount = _to_decimal(payment_row["amount"]).quantize(Decimal("0.01"))
            if refunded_amount < payment_amount:
                return
            await self._db.execute(
                sa.text(
                    """
                    UPDATE payments
                    SET status = 'refunded'
                    WHERE id = :payment_id
                    """
                ),
                {"payment_id": _to_uuid(payment_row["id"])},
            )

    @beartype
    async def _get_order_refund_total(self, *, order_id: UUID) -> Decimal:
        result = await self._db.execute(
            sa.text(
                """
                SELECT COALESCE(SUM(amount), 0) AS refunded_amount
                FROM refunds
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id},
        )
        value = result.scalar_one_or_none()
        if value is None:
            return Decimal("0.00")
        return _to_decimal(value).quantize(Decimal("0.01"))

    @beartype
    async def _get_latest_payment(self, *, order_id: UUID) -> Mapping[str, object] | None:
        result = await self._db.execute(
            sa.text(
                """
                SELECT id, external_payment_id, status, amount
                FROM payments
                WHERE order_id = :order_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"order_id": order_id},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return row

    @beartype
    async def _notify_buyer_status_change(
        self,
        *,
        order: Mapping[str, object],
        status: str,
        tracking_number: str | None = None,
    ) -> None:
        email = cast(str | None, order["buyer_email"])
        if not email:
            return

        order_number = f"ORD-{str(order['id'])[:8].upper()}"
        details_map: dict[str, str] = {
            "paid": "Оплата получена, заказ передан бренду.",
            "processing": "Бренд подтвердил наличие и собирает заказ.",
            "shipped": "Заказ отправлен, отслеживайте доставку по трек-номеру.",
            "delivered": "Заказ доставлен.",
            "completed": "Заказ завершен.",
            "cancelled_by_buyer": "Заказ отменен по вашему запросу.",
            "cancelled_by_brand": "Заказ отменен брендом.",
            "returned": "Заказ отмечен как возврат.",
        }
        try:
            await self._notification_service.notify_buyer_status_update(
                email=email,
                order_number=order_number,
                status=status,
                details=details_map.get(status, "Статус заказа обновлен."),
                tracking_number=tracking_number,
            )
        except Exception:
            # Notification transport errors should not roll back order state.
            return

    @beartype
    def _status_payload_from_order(self, *, order: Mapping[str, object]) -> dict[str, object]:
        return {
            "id": _to_uuid(order["id"]),
            "status": str(order["status"]),
            "paid_at": cast(datetime | None, order["paid_at"]),
            "shipped_at": cast(datetime | None, order["shipped_at"]),
            "delivered_at": cast(datetime | None, order["delivered_at"]),
        }

    @beartype
    def _format_delivery_address(self, delivery_address_json: object) -> str:
        if not isinstance(delivery_address_json, dict):
            return ""
        address = cast(Mapping[str, object], delivery_address_json)
        parts = [
            address.get("city"),
            address.get("street"),
            address.get("apartment"),
            address.get("postal_code"),
        ]
        normalized = [str(part).strip() for part in parts if part is not None and str(part).strip()]
        return ", ".join(normalized)

    # ------------------------------------------------------------------
    # Cart helpers for order creation
    # ------------------------------------------------------------------

    @beartype
    async def _fetch_cart_with_brand_commission(
        self, *, user_id: UUID
    ) -> list[Mapping[str, object]]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    ci.id AS cart_item_id,
                    ci.quantity,
                    pv.id AS variant_id,
                    pv.product_id,
                    pv.price_rub,
                    pv.stock_quantity,
                    pv.vendor_code,
                    pv.size,
                    pv.color,
                    pv.is_active AS variant_is_active,
                    p.name AS product_name,
                    p.is_active AS product_is_active,
                    b.id AS brand_id,
                    b.commission_rate,
                    b.is_active AS brand_is_active
                FROM cart_items ci
                JOIN product_variants pv ON pv.id = ci.product_variant_id
                JOIN products p ON p.id = pv.product_id
                JOIN brands b ON b.id = p.brand_id
                WHERE ci.user_id = :user_id
                ORDER BY ci.created_at ASC
                """
            ),
            {"user_id": user_id},
        )
        return result.mappings().all()

    @beartype
    async def _validate_stock_for_cart(self, *, cart_rows: list[Mapping[str, object]]) -> None:
        for row in cart_rows:
            if (
                not row["variant_is_active"]
                or not row["product_is_active"]
                or not row["brand_is_active"]
            ):
                raise ValueError(f"Product variant {row['variant_id']} is unavailable.")
            available = _to_int(row["stock_quantity"])
            requested = _to_int(row["quantity"])
            if requested > available:
                raise InsufficientStockError(
                    f"Insufficient stock for variant {row['variant_id']}: "
                    f"requested {requested}, available {available}."
                )

    @beartype
    async def _reserve_stock(self, *, cart_rows: list[Mapping[str, object]]) -> None:
        for row in cart_rows:
            result = await self._db.execute(
                sa.text(
                    """
                    UPDATE product_variants
                    SET stock_quantity = stock_quantity - :quantity
                    WHERE id = :variant_id
                      AND stock_quantity >= :quantity
                    RETURNING id
                    """
                ),
                {
                    "variant_id": _to_uuid(row["variant_id"]),
                    "quantity": _to_int(row["quantity"]),
                },
            )
            if result.mappings().first() is None:
                raise InsufficientStockError(
                    f"Failed to reserve stock for variant {row['variant_id']}: "
                    f"requested {_to_int(row['quantity'])}."
                )

    @beartype
    async def _clear_cart(self, *, user_id: UUID) -> None:
        await self._db.execute(
            sa.text("DELETE FROM cart_items WHERE user_id = :user_id"),
            {"user_id": user_id},
        )

    @beartype
    async def _get_user_address(self, *, user_id: UUID, address_id: UUID) -> Mapping[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT id, city, street, apartment, postal_code
                FROM addresses
                WHERE id = :address_id AND user_id = :user_id
                LIMIT 1
                """
            ),
            {"address_id": address_id, "user_id": user_id},
        )
        row = result.mappings().first()
        if row is None:
            raise AddressNotFoundError("Address not found.")
        return row

    @beartype
    def _delivery_address_for_cost(self, *, delivery_address_json: object) -> dict[str, str]:
        if not isinstance(delivery_address_json, dict):
            return {"city": "", "street": "", "apartment": "", "postal_code": ""}
        address = cast(Mapping[str, object], delivery_address_json)
        return {
            "city": str(address.get("city", "")).strip(),
            "street": str(address.get("street", "")).strip(),
            "apartment": str(address.get("apartment", "")).strip(),
            "postal_code": str(address.get("postal_code", "")).strip(),
        }
