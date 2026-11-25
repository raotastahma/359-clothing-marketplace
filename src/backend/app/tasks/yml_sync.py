from __future__ import annotations

# mypy: disable-error-code=untyped-decorator
# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
import asyncio
from typing import cast
from uuid import UUID

from app.core.database import async_session_factory
from app.services.yml_sync_service import (
    ConcurrentSyncError,
    DatabaseSessionProtocol,
    YmlSyncService,
)
from app.tasks.celery_app import celery_app


def _run(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


async def _sync_brand_feed(brand_id: str) -> dict[str, object]:
    async with async_session_factory() as session:
        service = YmlSyncService(db=cast(DatabaseSessionProtocol, session))
        return await service.sync_brand_feed(brand_id=UUID(brand_id))


async def _sync_all_due_feeds() -> int:
    async with async_session_factory() as session:
        service = YmlSyncService(db=cast(DatabaseSessionProtocol, session))
        return await service.sync_all_due_feeds()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    name="yml.sync_brand_feed",
)
def sync_brand_feed_task(self: object, *, brand_id: str) -> dict[str, object]:
    _ = self
    try:
        result = _run(_sync_brand_feed(brand_id))
        return cast(dict[str, object], result)
    except ConcurrentSyncError:
        return {"status": "skipped", "reason": "already_running", "brand_id": brand_id}


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
    name="yml.sync_all_due_feeds",
)
def sync_all_due_feeds_task(self: object) -> int:
    _ = self
    result = _run(_sync_all_due_feeds())
    return int(cast(int, result))
