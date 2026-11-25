from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast, runtime_checkable
from uuid import UUID

import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable

from app.services.order_service import (
    DatabaseSessionProtocol as OrderDatabaseSessionProtocol,
)
from app.services.order_service import (
    InvalidTransitionError,
    OrderService,
)


@dataclass(frozen=True, slots=True)
class OrderActionResult:
    order_id: UUID
    status: str
    title: str
    message: str


class TokenGoneError(ValueError):
    pass


class InvalidTokenError(ValueError):
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


class OrderActionService:
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
    async def confirm(self, *, token: str) -> OrderActionResult:
        token_row = await self._consume_token(
            token=token,
            expected_action_type="confirm",
            allowed_sub_order_statuses=frozenset({"paid"}),
            target_status="processing",
        )
        order_id = _to_uuid(token_row["order_id"])

        current = await self._order_service.sync_order_status_from_sub_orders(
            order_id=order_id,
            commit=False,
        )
        await self._db.commit()
        return OrderActionResult(
            order_id=order_id,
            status=str(current["status"]),
            title="Подтверждение принято",
            message="Подзаказ переведён в processing.",
        )

    @beartype
    async def cancel(self, *, token: str) -> OrderActionResult:
        token_row = await self._consume_token(
            token=token,
            expected_action_type="cancel",
            allowed_sub_order_statuses=frozenset({"paid", "processing"}),
            target_status="cancelled_by_brand",
        )
        order_id = _to_uuid(token_row["order_id"])
        brand_id = _to_uuid(token_row["brand_id"])
        current = await self._order_service.handle_sub_order_cancelled_by_brand(
            order_id=order_id,
            brand_id=brand_id,
            refund_from_status=str(
                token_row.get("previous_sub_order_status", token_row["sub_order_status"])
            ),
            commit=False,
        )
        await self._db.commit()
        return OrderActionResult(
            order_id=order_id,
            status=str(current["status"]),
            title="Подзаказ отменён",
            message="Отмена подзаказа зафиксирована.",
        )

    @beartype
    async def ship(self, *, token: str, tracking_number: str) -> OrderActionResult:
        normalized_tracking = tracking_number.strip()
        if not normalized_tracking:
            raise ValueError("tracking_number is required.")

        token_row = await self._consume_token(
            token=token,
            expected_action_type="ship",
            allowed_sub_order_statuses=frozenset({"processing"}),
            target_status="shipped",
            tracking_number=normalized_tracking,
        )
        order_id = _to_uuid(token_row["order_id"])

        current = await self._order_service.sync_order_status_from_sub_orders(
            order_id=order_id,
            tracking_number=normalized_tracking,
            commit=False,
        )
        await self._db.commit()
        return OrderActionResult(
            order_id=order_id,
            status=str(current["status"]),
            title="Подзаказ отправлен",
            message="Трек-номер сохранён.",
        )

    @beartype
    async def _consume_token(
        self,
        *,
        token: str,
        expected_action_type: str,
        allowed_sub_order_statuses: frozenset[str],
        target_status: str,
        tracking_number: str | None = None,
    ) -> Mapping[str, object]:
        row = await self._get_token_row(token=token)
        action_type = str(row["action_type"])
        if action_type != expected_action_type:
            raise InvalidTokenError("Token action type does not match endpoint.")

        expires_at = cast(datetime, row["expires_at"])
        used_at = cast(datetime | None, row["used_at"])
        now_utc = datetime.now(UTC)
        if used_at is not None or expires_at <= now_utc:
            raise TokenGoneError("Token expired or already used.")

        current_status = str(row["sub_order_status"])
        if current_status not in allowed_sub_order_statuses:
            raise InvalidTransitionError(
                current_status=current_status,
                target_status=target_status,
            )

        consumed_row = await self._transition_sub_order_and_consume_token(
            row=row,
            expected_action_type=expected_action_type,
            allowed_sub_order_statuses=allowed_sub_order_statuses,
            target_status=target_status,
            tracking_number=tracking_number,
            now_utc=now_utc,
        )
        if consumed_row is not None:
            return consumed_row

        refreshed_row = await self._get_token_row(token=token)
        refreshed_expires_at = cast(datetime, refreshed_row["expires_at"])
        refreshed_used_at = cast(datetime | None, refreshed_row["used_at"])
        if refreshed_used_at is not None or refreshed_expires_at <= now_utc:
            raise TokenGoneError("Token expired or already used.")

        refreshed_status = str(refreshed_row["sub_order_status"])
        raise InvalidTransitionError(
            current_status=refreshed_status,
            target_status=target_status,
        )

    @beartype
    async def _get_token_row(self, *, token: str) -> Mapping[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    oat.id,
                    oat.order_id,
                    oat.sub_order_id,
                    oat.brand_id,
                    oat.action_type,
                    oat.expires_at,
                    oat.used_at,
                    so.status AS sub_order_status
                FROM order_action_tokens oat
                JOIN sub_orders so ON so.id = oat.sub_order_id
                WHERE oat.token = :token
                LIMIT 1
                """
            ),
            {"token": token},
        )
        row = result.mappings().first()
        if row is None:
            raise InvalidTokenError("Token not found.")
        return row

    @beartype
    async def _transition_sub_order_and_consume_token(
        self,
        *,
        row: Mapping[str, object],
        expected_action_type: str,
        allowed_sub_order_statuses: frozenset[str],
        target_status: str,
        tracking_number: str | None = None,
        now_utc: datetime,
    ) -> Mapping[str, object] | None:
        update_parts = ["status = :target_status"]
        params: dict[str, object] = {
            "token_id": _to_uuid(row["id"]),
            "expected_action_type": expected_action_type,
            "target_status": target_status,
            "used_at": now_utc,
            "now_utc": now_utc,
        }

        if target_status == "processing":
            update_parts.append("confirmed_at = COALESCE(confirmed_at, :confirmed_at)")
            update_parts.append(
                "shipping_deadline = COALESCE(shipping_deadline, :shipping_deadline)"
            )
            params["confirmed_at"] = now_utc
            params["shipping_deadline"] = now_utc + timedelta(hours=48)
        elif target_status == "shipped":
            normalized_tracking = tracking_number.strip() if tracking_number is not None else ""
            if not normalized_tracking:
                raise ValueError("tracking_number is required for shipped sub_order.")
            update_parts.append("tracking_number = :tracking_number")
            update_parts.append("shipped_at = COALESCE(shipped_at, :shipped_at)")
            params["tracking_number"] = normalized_tracking
            params["shipped_at"] = now_utc
        elif target_status == "cancelled_by_brand":
            pass
        else:
            raise ValueError(f"Unsupported sub_order status: {target_status}")

        status_placeholders: list[str] = []
        for index, status in enumerate(sorted(allowed_sub_order_statuses)):
            key = f"allowed_status_{index}"
            status_placeholders.append(f":{key}")
            params[key] = status

        result = await self._db.execute(
            sa.text(
                f"""
                WITH token_row AS (
                    SELECT
                        oat.id,
                        oat.order_id,
                        oat.sub_order_id,
                        oat.brand_id,
                        oat.action_type,
                        oat.expires_at,
                        oat.used_at,
                        so.status AS sub_order_status
                    FROM order_action_tokens oat
                    JOIN sub_orders so ON so.id = oat.sub_order_id
                    WHERE oat.id = :token_id
                      AND oat.action_type = :expected_action_type
                      AND oat.used_at IS NULL
                      AND oat.expires_at > :now_utc
                      AND so.status IN ({", ".join(status_placeholders)})
                    LIMIT 1
                ),
                updated_sub_order AS (
                    UPDATE sub_orders so
                    SET {", ".join(update_parts)}
                    FROM token_row tr
                    WHERE so.id = tr.sub_order_id
                      AND so.status = tr.sub_order_status
                    RETURNING so.id
                ),
                used_token AS (
                    UPDATE order_action_tokens oat
                    SET used_at = :used_at
                    FROM token_row tr
                    JOIN updated_sub_order uso ON uso.id = tr.sub_order_id
                    WHERE oat.id = tr.id
                      AND oat.used_at IS NULL
                    RETURNING oat.id
                )
                SELECT
                    tr.id,
                    tr.order_id,
                    tr.sub_order_id,
                    tr.brand_id,
                    tr.action_type,
                    tr.expires_at,
                    :used_at AS used_at,
                    tr.sub_order_status AS previous_sub_order_status,
                    :target_status AS sub_order_status
                FROM token_row tr
                JOIN updated_sub_order uso ON uso.id = tr.sub_order_id
                JOIN used_token ut ON ut.id = tr.id
                """
            ),
            params,
        )
        return result.mappings().first()
