from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol, runtime_checkable
from uuid import UUID

import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable


class BrandNotFoundError(ValueError):
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


class FinanceService:
    @beartype
    def __init__(self, *, db: DatabaseSessionProtocol) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Platform-wide finance report for a date range
    # ------------------------------------------------------------------

    @beartype
    async def get_finance_report(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> dict[str, object]:
        date_to_exclusive = date_to + timedelta(days=1)
        totals_result = await self._db.execute(
            sa.text(
                """
                SELECT
                    COALESCE(SUM(so.items_total), 0) AS total_sales,
                    COALESCE(SUM(so.commission_total), 0) AS total_commission
                FROM sub_orders so
                WHERE so.status NOT IN ('pending', 'cancelled_by_buyer', 'cancelled_by_brand')
                  AND so.created_at >= :date_from
                  AND so.created_at < :date_to_exclusive
                """
            ),
            {
                "date_from": date_from,
                "date_to_exclusive": date_to_exclusive,
            },
        )
        totals = totals_result.mappings().first()
        total_sales = _to_decimal(totals["total_sales"]) if totals else Decimal("0.00")
        total_commission = _to_decimal(totals["total_commission"]) if totals else Decimal("0.00")

        payouts_result = await self._db.execute(
            sa.text(
                """
                SELECT
                    COALESCE(SUM(
                        CASE
                            WHEN p.status = 'completed'
                             AND p.completed_at >= :date_from
                             AND p.completed_at < :date_to_exclusive
                            THEN p.amount
                            ELSE 0
                        END
                    ), 0)
                        AS total_payouts_completed,
                    COALESCE(SUM(
                        CASE
                            WHEN p.status = 'pending'
                             AND p.created_at >= :date_from
                             AND p.created_at < :date_to_exclusive
                            THEN p.amount
                            ELSE 0
                        END
                    ), 0)
                        AS total_payouts_pending
                FROM payouts p
                WHERE (
                    p.status = 'completed'
                    AND p.completed_at >= :date_from
                    AND p.completed_at < :date_to_exclusive
                )
                OR (
                    p.status = 'pending'
                    AND p.created_at >= :date_from
                    AND p.created_at < :date_to_exclusive
                )
                """
            ),
            {
                "date_from": date_from,
                "date_to_exclusive": date_to_exclusive,
            },
        )
        payouts_totals = payouts_result.mappings().first()
        total_payouts_completed = (
            _to_decimal(payouts_totals["total_payouts_completed"])
            if payouts_totals
            else Decimal("0.00")
        )
        total_payouts_pending = (
            _to_decimal(payouts_totals["total_payouts_pending"])
            if payouts_totals
            else Decimal("0.00")
        )

        refunds_result = await self._db.execute(
            sa.text(
                """
                SELECT COALESCE(SUM(r.amount), 0) AS total_refunds
                FROM refunds r
                WHERE r.status = 'completed'
                  AND r.created_at >= :date_from
                  AND r.created_at < :date_to_exclusive
                """
            ),
            {
                "date_from": date_from,
                "date_to_exclusive": date_to_exclusive,
            },
        )
        refunds_row = refunds_result.mappings().first()
        total_refunds = (
            _to_decimal(refunds_row["total_refunds"]) if refunds_row else Decimal("0.00")
        )

        brands_result = await self._db.execute(
            sa.text(
                """
                SELECT
                    b.id AS brand_id,
                    b.name AS brand_name,
                    COALESCE(SUM(so.items_total), 0) AS sales,
                    COALESCE(SUM(so.commission_total), 0) AS commission,
                    COALESCE(
                        (SELECT SUM(p.amount) FROM payouts p
                         WHERE p.brand_id = b.id AND p.status = 'completed'
                           AND p.completed_at >= :date_from
                           AND p.completed_at < :date_to_exclusive),
                        0
                    ) AS payouts_completed,
                    COALESCE(
                        (SELECT SUM(p.amount) FROM payouts p
                         WHERE p.brand_id = b.id AND p.status = 'pending'
                           AND p.created_at >= :date_from
                           AND p.created_at < :date_to_exclusive),
                        0
                    ) AS payouts_pending
                FROM sub_orders so
                JOIN brands b ON b.id = so.brand_id
                WHERE so.status NOT IN ('pending', 'cancelled_by_buyer', 'cancelled_by_brand')
                  AND so.created_at >= :date_from
                  AND so.created_at < :date_to_exclusive
                GROUP BY b.id, b.name
                ORDER BY sales DESC
                """
            ),
            {
                "date_from": date_from,
                "date_to_exclusive": date_to_exclusive,
            },
        )

        brands_summary: list[dict[str, object]] = []
        for row in brands_result.mappings().all():
            brands_summary.append(
                {
                    "brand_id": _to_uuid(row["brand_id"]),
                    "brand_name": str(row["brand_name"]),
                    "sales": _to_decimal(row["sales"]).quantize(Decimal("0.01")),
                    "commission": _to_decimal(row["commission"]).quantize(Decimal("0.01")),
                    "payouts_completed": _to_decimal(row["payouts_completed"]).quantize(
                        Decimal("0.01")
                    ),
                    "payouts_pending": _to_decimal(row["payouts_pending"]).quantize(
                        Decimal("0.01")
                    ),
                }
            )

        return {
            "period": {"from": date_from, "to": date_to},
            "total_sales": total_sales.quantize(Decimal("0.01")),
            "total_commission": total_commission.quantize(Decimal("0.01")),
            "total_payouts_completed": total_payouts_completed.quantize(Decimal("0.01")),
            "total_payouts_pending": total_payouts_pending.quantize(Decimal("0.01")),
            "total_refunds": total_refunds.quantize(Decimal("0.01")),
            "brands_summary": brands_summary,
        }

    # ------------------------------------------------------------------
    # Brand balance summary
    # ------------------------------------------------------------------

    @beartype
    async def get_brand_balance(self, *, brand_id: UUID) -> dict[str, object]:
        brand_result = await self._db.execute(
            sa.text(
                """
                SELECT id, name, commission_rate
                FROM brands
                WHERE id = :brand_id
                LIMIT 1
                """
            ),
            {"brand_id": brand_id},
        )
        brand = brand_result.mappings().first()
        if brand is None:
            raise BrandNotFoundError("Brand not found.")

        earned_result = await self._db.execute(
            sa.text(
                """
                SELECT
                    COALESCE(SUM(so.items_total - so.commission_total), 0)
                        AS total_earned
                FROM sub_orders so
                WHERE so.brand_id = :brand_id
                  AND so.status NOT IN ('pending', 'cancelled_by_buyer', 'cancelled_by_brand')
                """
            ),
            {"brand_id": brand_id},
        )
        earned_row = earned_result.mappings().first()
        total_earned = _to_decimal(earned_row["total_earned"]) if earned_row else Decimal("0.00")

        payouts_result = await self._db.execute(
            sa.text(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0)
                        AS total_paid,
                    COALESCE(SUM(CASE WHEN status = 'pending' THEN amount ELSE 0 END), 0)
                        AS pending_payout
                FROM payouts
                WHERE brand_id = :brand_id
                """
            ),
            {"brand_id": brand_id},
        )
        payouts_row = payouts_result.mappings().first()
        total_paid = _to_decimal(payouts_row["total_paid"]) if payouts_row else Decimal("0.00")
        pending_payout = (
            _to_decimal(payouts_row["pending_payout"]) if payouts_row else Decimal("0.00")
        )

        recent_result = await self._db.execute(
            sa.text(
                """
                SELECT
                    p.id, p.sub_order_id, p.amount, p.status, p.payout_delay_days,
                    p.scheduled_at, p.completed_at, p.created_at
                FROM payouts p
                WHERE p.brand_id = :brand_id
                ORDER BY p.created_at DESC
                LIMIT 5
                """
            ),
            {"brand_id": brand_id},
        )
        recent_payouts: list[dict[str, object]] = []
        for row in recent_result.mappings().all():
            raw_status = str(row["status"])
            recent_payouts.append(
                {
                    "id": _to_uuid(row["id"]),
                    "brand_id": _to_uuid(brand["id"]),
                    "brand_name": str(brand["name"]),
                    "sub_order_id": _to_uuid(row["sub_order_id"]),
                    "amount": _to_decimal(row["amount"]),
                    "status": "paid" if raw_status == "completed" else raw_status,
                    "payout_delay_days": _to_int(row["payout_delay_days"]),
                    "scheduled_at": row["scheduled_at"],
                    "completed_at": row["completed_at"],
                    "created_at": row["created_at"],
                }
            )

        return {
            "brand_id": _to_uuid(brand["id"]),
            "brand_name": str(brand["name"]),
            "commission_rate": _to_decimal(brand["commission_rate"]),
            "total_earned": total_earned.quantize(Decimal("0.01")),
            "total_paid": total_paid.quantize(Decimal("0.01")),
            "pending_payout": pending_payout.quantize(Decimal("0.01")),
            "recent_payouts": recent_payouts,
        }
