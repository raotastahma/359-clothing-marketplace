"""Admin finance API routes for payout review and platform finance reporting."""

from __future__ import annotations

from datetime import date
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_scope
from app.schemas.finance import (
    BrandBalanceResponse,
    FinanceReportResponse,
)
from app.schemas.payout import (
    PaginationMeta,
    PayoutListResponse,
    PayoutMarkPaidRequest,
    PayoutResponse,
    PayoutStatusLiteral,
)
from app.services.finance_service import (
    BrandNotFoundError,
    FinanceService,
)
from app.services.finance_service import (
    DatabaseSessionProtocol as FinanceDatabaseSessionProtocol,
)
from app.services.payout_service import (
    DatabaseSessionProtocol as PayoutDatabaseSessionProtocol,
)
from app.services.payout_service import (
    PayoutAlreadyCompletedError,
    PayoutNotFoundError,
    PayoutService,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin:finance"],
    dependencies=[Depends(require_scope("admin"))],
)


@router.get("/payouts", response_model=PayoutListResponse)
async def list_payouts(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    brand_id: UUID | None = Query(default=None),
    payout_status: PayoutStatusLiteral | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> PayoutListResponse:
    service = PayoutService(db=cast(PayoutDatabaseSessionProtocol, db))
    items, total = await service.list_payouts(
        page=page,
        per_page=per_page,
        brand_id=brand_id,
        status_filter=payout_status,
    )
    return PayoutListResponse(
        data=items,  # type: ignore[arg-type]
        meta=PaginationMeta(page=page, per_page=per_page, total=total),
    )


@router.patch("/payouts/{payout_id}", response_model=PayoutResponse)
async def mark_payout_paid(
    payout_id: UUID,
    payload: PayoutMarkPaidRequest,
    db: AsyncSession = Depends(get_db),
) -> PayoutResponse:
    service = PayoutService(db=cast(PayoutDatabaseSessionProtocol, db))
    try:
        result = await service.mark_payout_paid(payout_id=payout_id)
    except PayoutNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PayoutAlreadyCompletedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return PayoutResponse(data=result)  # type: ignore[arg-type]


@router.get("/finance/report", response_model=FinanceReportResponse)
async def finance_report(
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    db: AsyncSession = Depends(get_db),
) -> FinanceReportResponse:
    service = FinanceService(db=cast(FinanceDatabaseSessionProtocol, db))
    result = await service.get_finance_report(date_from=date_from, date_to=date_to)
    return FinanceReportResponse(data=result)  # type: ignore[arg-type]


@router.get("/brands/{brand_id}/balance", response_model=BrandBalanceResponse)
async def brand_balance(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> BrandBalanceResponse:
    service = FinanceService(db=cast(FinanceDatabaseSessionProtocol, db))
    try:
        result = await service.get_brand_balance(brand_id=brand_id)
    except BrandNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BrandBalanceResponse(data=result)  # type: ignore[arg-type]
