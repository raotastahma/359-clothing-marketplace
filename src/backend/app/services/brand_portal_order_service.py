from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol, cast, runtime_checkable
from uuid import UUID

import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable

from app.services.order_service import (
    DatabaseSessionProtocol as OrderDatabaseSessionProtocol,
)
from app.services.order_service import InvalidTransitionError, OrderService

BRAND_PORTAL_ORDER_STATUSES = frozenset(
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
SLA_AT_RISK_WINDOW = timedelta(hours=2)


class BrandPortalOrderNotFoundError(ValueError):
    pass


@runtime_checkable
class MappingResultProtocol(Protocol):
    def first(self) -> Mapping[str, object] | None: ...

    def all(self) -> list[Mapping[str, object]]: ...


@runtime_checkable
class ExecuteResultProtocol(Protocol):
    def mappings(self) -> MappingResultProtocol: ...


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
def _active_sla_deadline(
    *,
    status: str,
    confirmation_deadline: datetime | None,
    shipping_deadline: datetime | None,
) -> datetime | None:
    if status == "paid":
        return confirmation_deadline
    if status == "processing":
        return shipping_deadline
    return None


@beartype
def _sla_status(
    *,
    status: str,
    confirmation_deadline: datetime | None,
    shipping_deadline: datetime | None,
    now_utc: datetime,
) -> str:
    deadline = _active_sla_deadline(
        status=status,
        confirmation_deadline=confirmation_deadline,
        shipping_deadline=shipping_deadline,
    )
    if deadline is None:
        return "on_time"
    if deadline <= now_utc:
        return "overdue"
    if deadline - now_utc < SLA_AT_RISK_WINDOW:
        return "at_risk"
    return "on_time"


class BrandPortalOrderService:
    @beartype
    def __init__(
        self,
        *,
        db: DatabaseSessionProtocol,
        order_service: OrderService | None = None,
    ) -> None:
        self._db = db
        self._order_service = order_service or OrderService(
            db=cast(OrderDatabaseSessionProtocol, db)
        )

    @beartype
    async def list_brand_orders(
        self,
        *,
        brand_id: UUID,
        page: int,
        per_page: int,
        status_filter: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[dict[str, object]], int]:
        where_parts = ["so.brand_id = :brand_id"]
        params: dict[str, object] = {"brand_id": brand_id}

        if status_filter is not None:
            if status_filter not in BRAND_PORTAL_ORDER_STATUSES:
                return [], 0
            where_parts.append("so.status = :status_filter")
            params["status_filter"] = status_filter
        if date_from is not None:
            where_parts.append("so.created_at >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            where_parts.append("so.created_at <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(where_parts)
        count_result = await self._db.execute(
            sa.text(f"SELECT COUNT(*) AS cnt FROM sub_orders so WHERE {where_clause}"),
            params,
        )
        count_row = count_result.mappings().first()
        total = _to_int(count_row["cnt"]) if count_row else 0

        params["limit"] = per_page
        params["offset"] = (page - 1) * per_page
        result = await self._db.execute(
            sa.text(
                f"""
                SELECT
                    so.id,
                    so.order_id,
                    so.brand_id,
                    so.status,
                    so.items_total,
                    so.commission_total,
                    so.tracking_number,
                    so.confirmation_deadline,
                    so.shipping_deadline,
                    so.confirmed_at,
                    so.shipped_at,
                    so.created_at
                FROM sub_orders so
                WHERE {where_clause}
                ORDER BY so.created_at DESC, so.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        rows = result.mappings().all()
        items_by_sub_order = await self._fetch_items_by_sub_order(
            sub_order_ids=[_to_uuid(row["id"]) for row in rows],
            brand_id=brand_id,
        )
        return [
            self._order_payload(row=row, items_by_sub_order=items_by_sub_order) for row in rows
        ], total

    @beartype
    async def get_brand_order_detail(
        self,
        *,
        brand_id: UUID,
        sub_order_id: UUID,
    ) -> dict[str, object]:
        row = await self._get_brand_sub_order_row(brand_id=brand_id, sub_order_id=sub_order_id)
        items_by_sub_order = await self._fetch_items_by_sub_order(
            sub_order_ids=[sub_order_id],
            brand_id=brand_id,
        )
        return self._order_payload(
            row=row,
            items_by_sub_order=items_by_sub_order,
            include_detail=True,
        )

    @beartype
    async def confirm_sub_order(
        self,
        *,
        brand_id: UUID,
        sub_order_id: UUID,
    ) -> dict[str, object]:
        now_utc = datetime.now(UTC)
        row = await self._transition_sub_order(
            brand_id=brand_id,
            sub_order_id=sub_order_id,
            expected_status="paid",
            target_status="processing",
            update_parts=[
                "confirmed_at = COALESCE(confirmed_at, :confirmed_at)",
            ],
            params={"confirmed_at": now_utc},
        )
        await self._order_service.sync_order_status_from_sub_orders(
            order_id=_to_uuid(row["order_id"]),
            commit=False,
        )
        await self._db.commit()
        return self._action_payload(row=row)

    @beartype
    async def ship_sub_order(
        self,
        *,
        brand_id: UUID,
        sub_order_id: UUID,
        tracking_number: str,
    ) -> dict[str, object]:
        normalized_tracking = tracking_number.strip()
        if not normalized_tracking:
            raise ValueError("tracking_number is required.")

        now_utc = datetime.now(UTC)
        row = await self._transition_sub_order(
            brand_id=brand_id,
            sub_order_id=sub_order_id,
            expected_status="processing",
            target_status="shipped",
            update_parts=[
                "tracking_number = :tracking_number",
                "shipped_at = COALESCE(shipped_at, :shipped_at)",
            ],
            params={"tracking_number": normalized_tracking, "shipped_at": now_utc},
        )
        await self._order_service.sync_order_status_from_sub_orders(
            order_id=_to_uuid(row["order_id"]),
            tracking_number=normalized_tracking,
            commit=False,
        )
        await self._db.commit()
        return self._action_payload(row=row)

    @beartype
    async def _get_brand_sub_order_row(
        self,
        *,
        brand_id: UUID,
        sub_order_id: UUID,
    ) -> Mapping[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    so.id,
                    so.order_id,
                    so.brand_id,
                    so.status,
                    so.items_total,
                    so.commission_total,
                    so.tracking_number,
                    so.confirmation_deadline,
                    so.shipping_deadline,
                    so.confirmed_at,
                    so.shipped_at,
                    so.created_at,
                    o.delivery_address_json
                FROM sub_orders so
                JOIN orders o ON o.id = so.order_id
                WHERE so.id = :sub_order_id
                  AND so.brand_id = :brand_id
                LIMIT 1
                """
            ),
            {"sub_order_id": sub_order_id, "brand_id": brand_id},
        )
        row = result.mappings().first()
        if row is None:
            raise BrandPortalOrderNotFoundError("Sub-order not found.")
        return row

    @beartype
    async def _fetch_items_by_sub_order(
        self,
        *,
        sub_order_ids: Sequence[UUID],
        brand_id: UUID,
    ) -> dict[UUID, list[dict[str, object]]]:
        if not sub_order_ids:
            return {}

        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    oi.sub_order_id,
                    p.name AS product_name,
                    pv.size,
                    oi.quantity,
                    oi.unit_price,
                    pi.url AS image_url
                FROM order_items oi
                JOIN product_variants pv ON pv.id = oi.product_variant_id
                JOIN products p ON p.id = pv.product_id
                LEFT JOIN LATERAL (
                    SELECT url
                    FROM product_images
                    WHERE product_id = p.id
                    ORDER BY sort_order ASC, id ASC
                    LIMIT 1
                ) pi ON TRUE
                WHERE oi.sub_order_id IN :sub_order_ids
                  AND oi.brand_id = :brand_id
                ORDER BY oi.sub_order_id ASC, oi.id ASC
                """
            ).bindparams(sa.bindparam("sub_order_ids", expanding=True)),
            {"sub_order_ids": list(sub_order_ids), "brand_id": brand_id},
        )
        grouped: dict[UUID, list[dict[str, object]]] = {
            sub_order_id: [] for sub_order_id in sub_order_ids
        }
        for row in result.mappings().all():
            sub_order_id = _to_uuid(row["sub_order_id"])
            grouped.setdefault(sub_order_id, []).append(
                {
                    "product_name": str(row["product_name"]),
                    "size": str(row["size"]),
                    "quantity": _to_int(row["quantity"]),
                    "unit_price": _to_decimal(row["unit_price"]),
                    "image_url": cast(str | None, row["image_url"]),
                }
            )
        return grouped

    @beartype
    async def _transition_sub_order(
        self,
        *,
        brand_id: UUID,
        sub_order_id: UUID,
        expected_status: str,
        target_status: str,
        update_parts: list[str],
        params: Mapping[str, object],
    ) -> Mapping[str, object]:
        update_sql = ", ".join(["status = :target_status", *update_parts])
        query_params: dict[str, object] = {
            "brand_id": brand_id,
            "sub_order_id": sub_order_id,
            "expected_status": expected_status,
            "target_status": target_status,
            **dict(params),
        }
        result = await self._db.execute(
            sa.text(
                f"""
                UPDATE sub_orders
                SET {update_sql}
                WHERE id = :sub_order_id
                  AND brand_id = :brand_id
                  AND status = :expected_status
                RETURNING
                    id,
                    order_id,
                    brand_id,
                    status,
                    items_total,
                    commission_total,
                    tracking_number,
                    confirmation_deadline,
                    shipping_deadline,
                    confirmed_at,
                    shipped_at,
                    created_at
                """
            ),
            query_params,
        )
        row = result.mappings().first()
        if row is not None:
            return row

        current = await self._get_brand_sub_order_row(
            brand_id=brand_id,
            sub_order_id=sub_order_id,
        )
        raise InvalidTransitionError(
            current_status=str(current["status"]),
            target_status=target_status,
        )

    @beartype
    def _order_payload(
        self,
        *,
        row: Mapping[str, object],
        items_by_sub_order: Mapping[UUID, list[dict[str, object]]],
        include_detail: bool = False,
    ) -> dict[str, object]:
        sub_order_id = _to_uuid(row["id"])
        items_total = _to_decimal(row["items_total"])
        commission_total = _to_decimal(row["commission_total"])
        payload: dict[str, object] = {
            "id": sub_order_id,
            "parent_order_id": _to_uuid(row["order_id"]),
            "status": str(row["status"]),
            "items": items_by_sub_order.get(sub_order_id, []),
            "items_total": items_total,
            "commission_total": commission_total,
            "payout_amount": (items_total - commission_total).quantize(Decimal("0.01")),
            "confirmation_deadline": cast(datetime | None, row["confirmation_deadline"]),
            "shipping_deadline": cast(datetime | None, row["shipping_deadline"]),
            "sla_status": _sla_status(
                status=str(row["status"]),
                confirmation_deadline=cast(datetime | None, row["confirmation_deadline"]),
                shipping_deadline=cast(datetime | None, row["shipping_deadline"]),
                now_utc=datetime.now(UTC),
            ),
            "created_at": cast(datetime, row["created_at"]),
        }
        if include_detail:
            payload["delivery_address"] = cast(
                dict[str, object] | None,
                row["delivery_address_json"],
            )
            payload["tracking_number"] = cast(str | None, row["tracking_number"])
            payload["confirmed_at"] = cast(datetime | None, row["confirmed_at"])
            payload["shipped_at"] = cast(datetime | None, row["shipped_at"])
        return payload

    @beartype
    def _action_payload(self, *, row: Mapping[str, object]) -> dict[str, object]:
        return {
            "id": _to_uuid(row["id"]),
            "status": str(row["status"]),
            "confirmation_deadline": cast(datetime | None, row["confirmation_deadline"]),
            "shipping_deadline": cast(datetime | None, row["shipping_deadline"]),
            "sla_status": _sla_status(
                status=str(row["status"]),
                confirmation_deadline=cast(datetime | None, row["confirmation_deadline"]),
                shipping_deadline=cast(datetime | None, row["shipping_deadline"]),
                now_utc=datetime.now(UTC),
            ),
            "confirmed_at": cast(datetime | None, row["confirmed_at"]),
            "tracking_number": cast(str | None, row["tracking_number"]),
            "shipped_at": cast(datetime | None, row["shipped_at"]),
        }
