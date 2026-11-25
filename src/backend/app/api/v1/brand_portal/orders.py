from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.brand_portal.auth import BrandPortalContext, require_brand_role
from app.core.database import get_db
from app.schemas.brand_portal_order import (
    BrandPortalOrderActionResponse,
    BrandPortalOrderDetailResponse,
    BrandPortalOrderListResponse,
    BrandPortalOrderShipRequest,
)
from app.schemas.order import OrderStatusLiteral, PaginationMeta
from app.services.brand_portal_order_service import (
    BrandPortalOrderNotFoundError,
    BrandPortalOrderService,
)
from app.services.brand_portal_order_service import (
    DatabaseSessionProtocol as BrandPortalOrderDatabaseSessionProtocol,
)
from app.services.order_service import InvalidTransitionError

router = APIRouter(prefix="/brand-portal/orders", tags=["brand-portal:orders"])


@router.get("", response_model=BrandPortalOrderListResponse)
async def list_orders(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status_filter: OrderStatusLiteral | None = Query(default=None, alias="status"),
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> BrandPortalOrderListResponse:
    service = BrandPortalOrderService(db=cast(BrandPortalOrderDatabaseSessionProtocol, db))
    items, total = await service.list_brand_orders(
        brand_id=context.brand_id,
        page=page,
        per_page=per_page,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
    )
    return BrandPortalOrderListResponse(
        data=items,  # type: ignore[arg-type]
        meta=PaginationMeta(page=page, per_page=per_page, total=total),
    )


@router.get("/{sub_order_id}", response_model=BrandPortalOrderDetailResponse)
async def get_order(
    sub_order_id: UUID,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> BrandPortalOrderDetailResponse:
    service = BrandPortalOrderService(db=cast(BrandPortalOrderDatabaseSessionProtocol, db))
    try:
        result = await service.get_brand_order_detail(
            brand_id=context.brand_id,
            sub_order_id=sub_order_id,
        )
    except BrandPortalOrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BrandPortalOrderDetailResponse(data=result)  # type: ignore[arg-type]


@router.post("/{sub_order_id}/confirm", response_model=BrandPortalOrderActionResponse)
async def confirm_order(
    sub_order_id: UUID,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager")),
    db: AsyncSession = Depends(get_db),
) -> BrandPortalOrderActionResponse:
    service = BrandPortalOrderService(db=cast(BrandPortalOrderDatabaseSessionProtocol, db))
    try:
        result = await service.confirm_sub_order(
            brand_id=context.brand_id,
            sub_order_id=sub_order_id,
        )
    except BrandPortalOrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    return BrandPortalOrderActionResponse(data=result)  # type: ignore[arg-type]


@router.post("/{sub_order_id}/ship", response_model=BrandPortalOrderActionResponse)
async def ship_order(
    sub_order_id: UUID,
    payload: BrandPortalOrderShipRequest,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager")),
    db: AsyncSession = Depends(get_db),
) -> BrandPortalOrderActionResponse:
    service = BrandPortalOrderService(db=cast(BrandPortalOrderDatabaseSessionProtocol, db))
    try:
        result = await service.ship_sub_order(
            brand_id=context.brand_id,
            sub_order_id=sub_order_id,
            tracking_number=payload.tracking_number,
        )
    except BrandPortalOrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BrandPortalOrderActionResponse(data=result)  # type: ignore[arg-type]
