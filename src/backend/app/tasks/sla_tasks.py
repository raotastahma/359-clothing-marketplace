from __future__ import annotations

# mypy: disable-error-code=untyped-decorator
# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
import asyncio
from collections.abc import Mapping
from typing import Protocol, cast, runtime_checkable

import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable

from app.core.config import settings
from app.core.database import async_session_factory
from app.tasks.celery_app import celery_app


@runtime_checkable
class MappingResultProtocol(Protocol):
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


@runtime_checkable
class SlaNotificationServiceProtocol(Protocol):
    async def send_sla_alert(
        self,
        *,
        to: str,
        sub_order: Mapping[str, object],
        alert_type: str,
    ) -> None: ...


def _run(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


@beartype
async def check_sla_deadlines(
    *,
    db: DatabaseSessionProtocol,
    notification_service: SlaNotificationServiceProtocol | None = None,
    head_of_partnerships_email: str | None = None,
) -> int:
    alert_email = (head_of_partnerships_email or settings.head_of_partnerships_email).strip()
    if not alert_email:
        return 0

    if notification_service is None:
        from app.services.notification_service import NotificationService

        service: SlaNotificationServiceProtocol = NotificationService()
    else:
        service = notification_service
    sent_count = 0

    overdue_confirmation = await db.execute(
        sa.text(
            """
            SELECT
                so.id,
                so.order_id,
                so.brand_id,
                b.name AS brand_name,
                so.status,
                so.confirmation_deadline,
                so.shipping_deadline
            FROM sub_orders so
            JOIN brands b ON b.id = so.brand_id
            WHERE so.status = 'paid'
              AND so.confirmation_deadline < now()
            ORDER BY so.confirmation_deadline ASC, so.id ASC
            """
        )
    )
    for sub_order in overdue_confirmation.mappings().all():
        await service.send_sla_alert(
            to=alert_email,
            sub_order=sub_order,
            alert_type="confirmation_overdue",
        )
        sent_count += 1

    overdue_shipping = await db.execute(
        sa.text(
            """
            SELECT
                so.id,
                so.order_id,
                so.brand_id,
                b.name AS brand_name,
                so.status,
                so.confirmation_deadline,
                so.shipping_deadline
            FROM sub_orders so
            JOIN brands b ON b.id = so.brand_id
            WHERE so.status = 'processing'
              AND so.shipping_deadline < now()
            ORDER BY so.shipping_deadline ASC, so.id ASC
            """
        )
    )
    for sub_order in overdue_shipping.mappings().all():
        await service.send_sla_alert(
            to=alert_email,
            sub_order=sub_order,
            alert_type="shipping_overdue",
        )
        sent_count += 1

    return sent_count


async def _check_sla_deadlines() -> int:
    async with async_session_factory() as session:
        return await check_sla_deadlines(db=cast(DatabaseSessionProtocol, session))


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    name="sla.check_deadlines",
)
def check_sla_deadlines_task(self: object) -> int:
    _ = self
    result = _run(_check_sla_deadlines())
    return int(cast(int, result))
