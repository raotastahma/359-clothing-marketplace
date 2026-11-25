from __future__ import annotations

# mypy: disable-error-code=untyped-decorator
# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.integrations.delivery import get_delivery_provider
from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    name="delivery.refresh_tracking_statuses",
)
def refresh_tracking_statuses_task(self: object, *, limit: int = 100) -> int:
    _ = self
    if limit <= 0:
        return 0

    return asyncio.run(_refresh_tracking_statuses(limit=limit))


async def _refresh_tracking_statuses(*, limit: int) -> int:
    provider = get_delivery_provider()
    engine = create_async_engine(settings.database_url)
    updated_count = 0

    try:
        async with engine.begin() as connection:
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT id, order_id, tracking_number
                        FROM sub_orders
                        WHERE status = 'shipped'
                          AND tracking_number IS NOT NULL
                        ORDER BY shipped_at DESC NULLS LAST, created_at DESC
                        LIMIT :limit
                        """
                    ),
                    {"limit": limit},
                )
            ).mappings()

            for row in rows:
                tracking_number = str(row["tracking_number"])
                remote_status = await provider.get_tracking_status(tracking_number=tracking_number)
                if remote_status in {"delivered", "completed"}:
                    update_result = await connection.execute(
                        text(
                            """
                            UPDATE sub_orders
                            SET status = 'delivered',
                                delivered_at = COALESCE(delivered_at, now())
                            WHERE id = :sub_order_id
                              AND status = 'shipped'
                            RETURNING order_id
                            """
                        ),
                        {"sub_order_id": row["id"]},
                    )
                    updated_row = update_result.mappings().first()
                    if updated_row is None:
                        continue
                    await connection.execute(
                        text(
                            """
                            UPDATE orders o
                            SET status = 'delivered',
                                delivered_at = COALESCE(delivered_at, now())
                            WHERE o.id = :order_id
                              AND o.status <> 'completed'
                              AND NOT EXISTS (
                                  SELECT 1
                                  FROM sub_orders so
                                  WHERE so.order_id = o.id
                                    AND so.status NOT IN ('delivered', 'completed')
                              )
                            """
                        ),
                        {"order_id": updated_row["order_id"]},
                    )
                    updated_count += 1
    finally:
        await engine.dispose()

    return updated_count
