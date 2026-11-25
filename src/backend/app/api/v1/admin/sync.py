from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_scope
from app.schemas.yml_sync import FeedSyncLogResponse, FeedSyncLogsResponse, PaginationMeta
from app.services.yml_sync_service import DatabaseSessionProtocol, YmlSyncService

router = APIRouter(
    prefix="/admin/brands/{brand_id}/sync-logs",
    tags=["admin:sync"],
    dependencies=[Depends(require_scope("admin"))],
)


@router.get("", response_model=FeedSyncLogsResponse)
async def list_brand_sync_logs(
    brand_id: UUID,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> FeedSyncLogsResponse:
    service = YmlSyncService(db=cast(DatabaseSessionProtocol, db))
    items, total = await service.list_logs(brand_id=brand_id, page=page, per_page=per_page)
    return FeedSyncLogsResponse(
        data=items,  # type: ignore[arg-type]
        meta=PaginationMeta(page=page, per_page=per_page, total=total),
    )


@router.get("/{log_id}", response_model=FeedSyncLogResponse)
async def get_brand_sync_log(
    brand_id: UUID,
    log_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FeedSyncLogResponse:
    service = YmlSyncService(db=cast(DatabaseSessionProtocol, db))
    try:
        payload = await service.get_log(brand_id=brand_id, log_id=log_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FeedSyncLogResponse(data=payload)  # type: ignore[arg-type]
