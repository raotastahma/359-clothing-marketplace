from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol, cast, runtime_checkable
from uuid import UUID

import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable


class PayoutNotFoundError(ValueError):
    pass


class PayoutAlreadyCompletedError(ValueError):
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
def next_payout_date(eligible_at: datetime) -> datetime:
    eligible_utc = (
        eligible_at.replace(tzinfo=UTC)
        if eligible_at.tzinfo is None
        else eligible_at.astimezone(UTC)
    )
    first_day = datetime(eligible_utc.year, eligible_utc.month, 1, tzinfo=UTC)
    fifteenth_day = datetime(eligible_utc.year, eligible_utc.month, 15, tzinfo=UTC)
    if eligible_utc.month == 12:
        next_first = datetime(eligible_utc.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_first = datetime(eligible_utc.year, eligible_utc.month + 1, 1, tzinfo=UTC)
    return min(
        candidate
        for candidate in (first_day, fifteenth_day, next_first)
        if candidate >= eligible_utc
    )


class PayoutService:
    @beartype
    def __init__(self, *, db: DatabaseSessionProtocol) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Auto-create payout when sub_order transitions to completed
    # ------------------------------------------------------------------

    @beartype
    async def create_payout_for_sub_order(
        self,
        *,
        sub_order_id: UUID,
    ) -> dict[str, object] | None:
        delay_days = await self._get_payout_delay_days()
        sub_order_result = await self._db.execute(
            sa.text(
                """
                SELECT
                    so.id AS sub_order_id,
                    so.order_id,
                    so.brand_id,
                    so.status,
                    so.items_total,
                    so.commission_total,
                    so.delivered_at,
                    b.name AS brand_name
                FROM sub_orders so
                JOIN brands b ON b.id = so.brand_id
                WHERE so.id = :sub_order_id
                """
            ),
            {"sub_order_id": sub_order_id},
        )
        row = sub_order_result.mappings().first()
        if row is None:
            raise PayoutNotFoundError("Sub-order not found.")
        if str(row["status"]) != "completed":
            raise ValueError("Payout can only be created for completed sub_order.")

        exists = await self._db.execute(
            sa.text(
                """
                SELECT 1 FROM payouts
                WHERE sub_order_id = :sub_order_id
                LIMIT 1
                """
            ),
            {"sub_order_id": sub_order_id},
        )
        if exists.scalar_one_or_none() is not None:
            return None

        order_id = _to_uuid(row["order_id"])
        brand_id = _to_uuid(row["brand_id"])
        delivered_at = cast(datetime | None, row["delivered_at"])
        if delivered_at is None:
            raise ValueError("Completed sub_order must have delivered_at.")
        scheduled_at = next_payout_date(delivered_at + timedelta(days=delay_days))
        payout_amount = (
            _to_decimal(row["items_total"]) - _to_decimal(row["commission_total"])
        ).quantize(Decimal("0.01"))

        await self._db.execute(
            sa.text(
                """
                INSERT INTO payouts (
                    brand_id, order_id, sub_order_id, amount, status,
                    payout_delay_days, scheduled_at
                )
                VALUES (
                    :brand_id, :order_id, :sub_order_id, :amount, 'pending',
                    :payout_delay_days, :scheduled_at
                )
                """
            ),
            {
                "brand_id": brand_id,
                "order_id": order_id,
                "sub_order_id": sub_order_id,
                "amount": payout_amount,
                "payout_delay_days": delay_days,
                "scheduled_at": scheduled_at,
            },
        )

        return {
            "brand_id": brand_id,
            "brand_name": str(row["brand_name"]),
            "sub_order_id": sub_order_id,
            "amount": payout_amount,
            "scheduled_at": scheduled_at,
        }

    # ------------------------------------------------------------------
    # Mark payout as paid (admin action)
    # ------------------------------------------------------------------

    @beartype
    async def mark_payout_paid(self, *, payout_id: UUID) -> dict[str, object]:
        payout = await self._get_payout(payout_id=payout_id)
        current_status = str(payout["status"])

        if current_status in {"paid", "completed"}:
            raise PayoutAlreadyCompletedError("Payout already completed.")
        if current_status not in {"pending"}:
            raise PayoutAlreadyCompletedError(
                f"Cannot mark payout as paid from status '{current_status}'."
            )

        now_utc = datetime.now(UTC)
        await self._db.execute(
            sa.text(
                """
                UPDATE payouts
                SET status = 'completed', completed_at = :completed_at
                WHERE id = :payout_id
                """
            ),
            {"payout_id": payout_id, "completed_at": now_utc},
        )
        await self._db.commit()

        return {
            "id": _to_uuid(payout["id"]),
            "brand_id": _to_uuid(payout["brand_id"]),
            "brand_name": str(payout["brand_name"]),
            "sub_order_id": _to_uuid(payout["sub_order_id"]),
            "amount": _to_decimal(payout["amount"]),
            "status": "paid",
            "payout_delay_days": _to_int(payout["payout_delay_days"]),
            "scheduled_at": cast(datetime, payout["scheduled_at"]),
            "completed_at": now_utc,
            "created_at": cast(datetime, payout["created_at"]),
        }

    # ------------------------------------------------------------------
    # List payouts (paginated, filtered)
    # ------------------------------------------------------------------

    @beartype
    async def list_payouts(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        brand_id: UUID | None = None,
        status_filter: str | None = None,
    ) -> tuple[list[dict[str, object]], int]:
        where_parts: list[str] = []
        params: dict[str, object] = {}

        if brand_id is not None:
            where_parts.append("p.brand_id = :brand_id")
            params["brand_id"] = brand_id
        if status_filter is not None:
            db_status = "completed" if status_filter == "paid" else status_filter
            where_parts.append("p.status = :status_filter")
            params["status_filter"] = db_status

        where_clause = (" AND ".join(where_parts)) if where_parts else "TRUE"

        count_result = await self._db.execute(
            sa.text(f"SELECT COUNT(*) AS cnt FROM payouts p WHERE {where_clause}"),
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
                    p.id, p.brand_id, b.name AS brand_name, p.sub_order_id,
                    p.amount, p.status, p.payout_delay_days,
                    p.scheduled_at, p.completed_at, p.created_at
                FROM payouts p
                JOIN brands b ON b.id = p.brand_id
                WHERE {where_clause}
                ORDER BY p.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )

        items: list[dict[str, object]] = []
        for row in result.mappings().all():
            raw_status = str(row["status"])
            display_status = "paid" if raw_status == "completed" else raw_status
            items.append(
                {
                    "id": _to_uuid(row["id"]),
                    "brand_id": _to_uuid(row["brand_id"]),
                    "brand_name": str(row["brand_name"]),
                    "sub_order_id": _to_uuid(row["sub_order_id"]),
                    "amount": _to_decimal(row["amount"]),
                    "status": display_status,
                    "payout_delay_days": _to_int(row["payout_delay_days"]),
                    "scheduled_at": cast(datetime, row["scheduled_at"]),
                    "completed_at": cast(datetime | None, row["completed_at"]),
                    "created_at": cast(datetime, row["created_at"]),
                }
            )

        return items, total

    # ------------------------------------------------------------------
    # Refund impact on payouts
    # ------------------------------------------------------------------

    @beartype
    async def handle_refund_impact(
        self,
        *,
        order_id: UUID,
        brand_id: UUID,
        refund_amount: Decimal,
        commission_refund: Decimal,
    ) -> None:
        payout_reduction = (refund_amount - commission_refund).quantize(Decimal("0.01"))

        payout_result = await self._db.execute(
            sa.text(
                """
                SELECT id, sub_order_id, status, amount
                FROM payouts
                WHERE order_id = :order_id AND brand_id = :brand_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"order_id": order_id, "brand_id": brand_id},
        )
        payout_row = payout_result.mappings().first()
        if payout_row is None:
            return

        payout_status = str(payout_row["status"])
        payout_id = _to_uuid(payout_row["id"])

        if payout_status == "pending":
            new_amount = (_to_decimal(payout_row["amount"]) - payout_reduction).quantize(
                Decimal("0.01")
            )
            if new_amount < Decimal("0.00"):
                new_amount = Decimal("0.00")
            await self._db.execute(
                sa.text("UPDATE payouts SET amount = :amount WHERE id = :payout_id"),
                {"amount": new_amount, "payout_id": payout_id},
            )
        elif payout_status == "completed":
            await self._db.execute(
                sa.text(
                    """
                    INSERT INTO payouts (
                        brand_id, order_id, sub_order_id, amount, status,
                        payout_delay_days, scheduled_at
                    )
                    VALUES (
                        :brand_id, :order_id, :sub_order_id, :amount, 'pending',
                        0, now()
                    )
                    """
                ),
                {
                    "brand_id": brand_id,
                    "order_id": order_id,
                    "sub_order_id": _to_uuid(payout_row["sub_order_id"]),
                    "amount": -payout_reduction,
                },
            )
        await self._db.commit()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @beartype
    async def _get_payout(self, *, payout_id: UUID) -> Mapping[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    p.id, p.brand_id, b.name AS brand_name, p.sub_order_id,
                    p.amount, p.status, p.payout_delay_days,
                    p.scheduled_at, p.completed_at, p.created_at
                FROM payouts p
                JOIN brands b ON b.id = p.brand_id
                WHERE p.id = :payout_id
                LIMIT 1
                """
            ),
            {"payout_id": payout_id},
        )
        row = result.mappings().first()
        if row is None:
            raise PayoutNotFoundError("Payout not found.")
        return row

    @beartype
    async def _get_payout_delay_days(self) -> int:
        result = await self._db.execute(
            sa.text(
                """
                SELECT value FROM platform_settings
                WHERE key = 'PAYOUT_DELAY_DAYS'
                LIMIT 1
                """
            )
        )
        row = result.mappings().first()
        if row is None:
            return 14
        return _to_int(row["value"])
