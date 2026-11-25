from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthenticatedUser, require_scope
from app.schemas.order import (
    OrderCreateRequest,
    OrderCreateResponse,
    OrderDetailResponse,
    OrderListResponse,
    OrderStatusResponse,
    PaginationMeta,
)
from app.services.order_service import (
    AddressNotFoundError,
    DatabaseSessionProtocol,
    EmptyCartError,
    InsufficientStockError,
    InvalidTransitionError,
    OrderNotFoundError,
    OrderService,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreateRequest,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),
    db: AsyncSession = Depends(get_db),
) -> OrderCreateResponse:
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    try:
        result = await service.create_order(
            user_id=current_user.id,
            address_id=payload.address_id,
            delivery_provider=payload.delivery_provider,
            delivery_method=payload.delivery_method,
            comment=payload.comment,
        )
    except EmptyCartError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AddressNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InsufficientStockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return OrderCreateResponse(data=result)  # type: ignore[arg-type]


@router.get("", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=100),
    order_status: str | None = Query(default=None, alias="status"),
    current_user: AuthenticatedUser = Depends(require_scope("customer")),
    db: AsyncSession = Depends(get_db),
) -> OrderListResponse:
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    items, total = await service.list_orders(
        user_id=current_user.id,
        page=page,
        per_page=per_page,
        status_filter=order_status,
    )
    return OrderListResponse(
        data=items,  # type: ignore[arg-type]
        meta=PaginationMeta(page=page, per_page=per_page, total=total),
    )


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order_detail(
    order_id: UUID,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),
    db: AsyncSession = Depends(get_db),
) -> OrderDetailResponse:
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    try:
        result = await service.get_order_detail(
            order_id=order_id,
            user_id=current_user.id,
        )
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return OrderDetailResponse(data=result)  # type: ignore[arg-type]


@router.post("/{order_id}/cancel", response_model=OrderStatusResponse)
async def cancel_order(
    order_id: UUID,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),
    db: AsyncSession = Depends(get_db),
) -> OrderStatusResponse:
    service = OrderService(db=cast(DatabaseSessionProtocol, db))
    try:
        payload = await service.cancel_by_buyer(order_id=order_id, user_id=current_user.id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return OrderStatusResponse(data=payload)  # type: ignore[arg-type]
