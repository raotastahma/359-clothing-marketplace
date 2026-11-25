from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol, runtime_checkable
from uuid import UUID

import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable

BRAND_PORTAL_PAYOUT_STATUSES = frozenset(
    {"pending", "scheduled", "processing", "completed", "paid", "failed"}
)


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


@beartype
def _to_decimal(value: object) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float, str)):
        return Decimal(str(value))
    raise TypeError("Expected decimal-compatible value.")


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
def _to_uuid(value: object) -> UUID:
    return UUID(str(value))


class BrandPortalFinanceService:
    @beartype
    def __init__(self, *, db: DatabaseSessionProtocol) -> None:
        self._db = db

    @beartype
    async def get_analytics_summary(
        self,
        *,
        brand_id: UUID,
        commission_rate: Decimal,
        date_from: date,
        date_to: date,
    ) -> dict[str, object]:
        date_to_exclusive = date_to + timedelta(days=1)
        sales_result = await self._db.execute(
            sa.text(
                """
                WITH item_totals AS (
                    SELECT
                        so.id AS sub_order_id,
                        so.items_total,
                        COALESCE(SUM(oi.commission_amount), 0) AS commission_total
                    FROM sub_orders so
                    LEFT JOIN order_items oi
                        ON oi.sub_order_id = so.id
                       AND oi.brand_id = :brand_id
                    WHERE so.brand_id = :brand_id
                      AND so.status NOT IN (
                          'pending',
                          'cancelled_by_buyer',
                          'cancelled_by_brand'
                      )
                      AND so.created_at >= :date_from
                      AND so.created_at < :date_to_exclusive
                    GROUP BY so.id, so.items_total
                )
                SELECT
                    COUNT(*) AS orders_count,
                    COALESCE(SUM(items_total), 0) AS total_sales,
                    COALESCE(SUM(commission_total), 0) AS commission_total
                FROM item_totals
                """
            ),
            {
                "brand_id": brand_id,
                "date_from": date_from,
                "date_to_exclusive": date_to_exclusive,
            },
        )
        sales_row = sales_result.mappings().first()
        orders_count = _to_int(sales_row["orders_count"]) if sales_row else 0
        total_sales = _to_decimal(sales_row["total_sales"]) if sales_row else Decimal("0.00")
        commission_total = (
            _to_decimal(sales_row["commission_total"]) if sales_row else Decimal("0.00")
        )

        payout_result = await self._db.execute(
            sa.text(
                """
                SELECT
                    COALESCE(SUM(
                        CASE
                            WHEN status = 'completed' THEN amount
                            ELSE 0
                        END
                    ), 0) AS payout_completed,
                    COALESCE(SUM(
                        CASE
                            WHEN status IN ('pending', 'scheduled', 'processing') THEN amount
                            ELSE 0
                        END
                    ), 0) AS payout_pending
                FROM payouts
                WHERE brand_id = :brand_id
                  AND created_at >= :date_from
                  AND created_at < :date_to_exclusive
                """
            ),
            {
                "brand_id": brand_id,
                "date_from": date_from,
                "date_to_exclusive": date_to_exclusive,
            },
        )
        payout_row = payout_result.mappings().first()
        payout_pending = (
            _to_decimal(payout_row["payout_pending"]) if payout_row else Decimal("0.00")
        )
        payout_completed = (
            _to_decimal(payout_row["payout_completed"]) if payout_row else Decimal("0.00")
        )

        return {
            "period": {"from": date_from, "to": date_to},
            "orders_count": orders_count,
            "total_sales": total_sales.quantize(Decimal("0.01")),
            "commission_rate": commission_rate,
            "commission_total": commission_total.quantize(Decimal("0.01")),
            "payout_pending": payout_pending.quantize(Decimal("0.01")),
            "payout_completed": payout_completed.quantize(Decimal("0.01")),
        }

    @beartype
    async def get_top_products(
        self,
        *,
        brand_id: UUID,
        date_from: date,
        date_to: date,
        limit: int,
    ) -> list[dict[str, object]]:
        date_to_exclusive = date_to + timedelta(days=1)
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    p.id AS product_id,
                    p.name AS product_name,
                    COALESCE(SUM(oi.quantity), 0)::int AS units_sold,
                    COALESCE(SUM(oi.unit_price * oi.quantity), 0) AS total_sales
                FROM order_items oi
                JOIN sub_orders so ON so.id = oi.sub_order_id
                JOIN product_variants pv ON pv.id = oi.product_variant_id
                JOIN products p ON p.id = pv.product_id
                WHERE so.brand_id = :brand_id
                  AND oi.brand_id = :brand_id
                  AND so.status NOT IN (
                      'pending',
                      'cancelled_by_buyer',
                      'cancelled_by_brand'
                  )
                  AND so.created_at >= :date_from
                  AND so.created_at < :date_to_exclusive
                GROUP BY p.id, p.name
                ORDER BY total_sales DESC, units_sold DESC, p.name ASC
                LIMIT :limit
                """
            ),
            {
                "brand_id": brand_id,
                "date_from": date_from,
                "date_to_exclusive": date_to_exclusive,
                "limit": limit,
            },
        )
        return [
            {
                "product_id": _to_uuid(row["product_id"]),
                "product_name": str(row["product_name"]),
                "units_sold": _to_int(row["units_sold"]),
                "total_sales": _to_decimal(row["total_sales"]).quantize(Decimal("0.01")),
            }
            for row in result.mappings().all()
        ]

    @beartype
    async def list_payouts(
        self,
        *,
        brand_id: UUID,
        page: int,
        per_page: int,
        status_filter: str | None = None,
    ) -> tuple[list[dict[str, object]], int]:
        where_parts = ["p.brand_id = :brand_id"]
        params: dict[str, object] = {"brand_id": brand_id}

        if status_filter is not None:
            if status_filter not in BRAND_PORTAL_PAYOUT_STATUSES:
                return [], 0
            db_status = "completed" if status_filter == "paid" else status_filter
            where_parts.append("p.status = :status_filter")
            params["status_filter"] = db_status

        where_clause = " AND ".join(where_parts)
        count_result = await self._db.execute(
            sa.text(f"SELECT COUNT(*) AS cnt FROM payouts p WHERE {where_clause}"),
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
                    p.id,
                    p.sub_order_id,
                    p.amount,
                    COALESCE(MAX(oi.commission_rate), 0) AS commission_rate,
                    p.status,
                    p.scheduled_at,
                    p.completed_at,
                    p.created_at
                FROM payouts p
                LEFT JOIN order_items oi ON oi.sub_order_id = p.sub_order_id
                WHERE {where_clause}
                GROUP BY
                    p.id,
                    p.sub_order_id,
                    p.amount,
                    p.status,
                    p.scheduled_at,
                    p.completed_at,
                    p.created_at
                ORDER BY p.created_at DESC, p.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )

        items: list[dict[str, object]] = []
        for row in result.mappings().all():
            items.append(
                {
                    "id": _to_uuid(row["id"]),
                    "sub_order_id": _to_uuid(row["sub_order_id"]),
                    "amount": _to_decimal(row["amount"]).quantize(Decimal("0.01")),
                    "commission_rate": _to_decimal(row["commission_rate"]),
                    "status": str(row["status"]),
                    "scheduled_at": row["scheduled_at"],
                    "completed_at": row["completed_at"],
                    "created_at": row["created_at"],
                }
            )
        return items, total
