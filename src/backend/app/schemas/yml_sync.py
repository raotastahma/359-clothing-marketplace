from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import PaginationMeta as PaginationMeta

FeedSyncStatusLiteral = Literal["running", "success", "error"]


class FeedSyncLogPayload(BaseModel):
    id: UUID
    brand_id: UUID
    started_at: datetime
    completed_at: datetime | None
    status: FeedSyncStatusLiteral
    updated_count: int
    unmatched_codes: list[str]
    error_message: str | None
    created_at: datetime


class FeedSyncLogResponse(BaseModel):
    data: FeedSyncLogPayload


class FeedSyncLogsResponse(BaseModel):
    data: list[FeedSyncLogPayload]
    meta: PaginationMeta
