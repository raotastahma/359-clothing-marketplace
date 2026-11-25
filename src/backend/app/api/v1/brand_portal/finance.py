from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.brand_portal.auth import BrandPortalContext, require_brand_role
from app.core.database import get_db
from app.schemas.brand_portal_finance import (
    BrandPortalPaginationMeta,
    BrandPortalPayoutListResponse,
)
from app.services.brand_portal_finance_service import (
    BrandPortalFinanceService,
)
from app.services.brand_portal_finance_service import (
    DatabaseSessionProtocol as BrandPortalFinanceDatabaseSessionProtocol,
)

router = APIRouter(prefix="/brand-portal/payouts", tags=["brand-portal:finance"])


@router.get("", response_model=BrandPortalPayoutListResponse)
async def list_payouts(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    payout_status: str | None = Query(default=None, alias="status"),
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> BrandPortalPayoutListResponse:
    service = BrandPortalFinanceService(db=cast(BrandPortalFinanceDatabaseSessionProtocol, db))
    items, total = await service.list_payouts(
        brand_id=context.brand_id,
        page=page,
        per_page=per_page,
        status_filter=payout_status,
    )
    return BrandPortalPayoutListResponse(
        data=items,  # type: ignore[arg-type]
        meta=BrandPortalPaginationMeta(page=page, per_page=per_page, total=total),
    )
