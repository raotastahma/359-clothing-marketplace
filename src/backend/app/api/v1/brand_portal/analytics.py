from __future__ import annotations

from datetime import date
from typing import cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.brand_portal.auth import BrandPortalContext, require_brand_role
from app.core.database import get_db
from app.schemas.brand_portal_finance import (
    BrandPortalAnalyticsSummaryResponse,
    BrandPortalTopProductsResponse,
)
from app.services.brand_portal_finance_service import (
    BrandPortalFinanceService,
)
from app.services.brand_portal_finance_service import (
    DatabaseSessionProtocol as BrandPortalFinanceDatabaseSessionProtocol,
)

router = APIRouter(prefix="/brand-portal/analytics", tags=["brand-portal:analytics"])


@router.get("/summary", response_model=BrandPortalAnalyticsSummaryResponse)
async def analytics_summary(
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> BrandPortalAnalyticsSummaryResponse:
    service = BrandPortalFinanceService(db=cast(BrandPortalFinanceDatabaseSessionProtocol, db))
    result = await service.get_analytics_summary(
        brand_id=context.brand_id,
        commission_rate=context.commission_rate,
        date_from=date_from,
        date_to=date_to,
    )
    return BrandPortalAnalyticsSummaryResponse(data=result)  # type: ignore[arg-type]


@router.get("/top-products", response_model=BrandPortalTopProductsResponse)
async def top_products(
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    limit: int = Query(default=10, ge=1, le=100),
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> BrandPortalTopProductsResponse:
    service = BrandPortalFinanceService(db=cast(BrandPortalFinanceDatabaseSessionProtocol, db))
    result = await service.get_top_products(
        brand_id=context.brand_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return BrandPortalTopProductsResponse(data=result)  # type: ignore[arg-type]
