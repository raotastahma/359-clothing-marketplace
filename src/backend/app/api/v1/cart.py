from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthenticatedUser, require_scope
from app.schemas.cart import CartItemCreateRequest, CartItemUpdateRequest, CartResponse
from app.services.cart_service import (
    CartItemNotFoundError,
    CartService,
    DatabaseSessionProtocol,
    InsufficientStockError,
)

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("/items", response_model=CartResponse)
async def get_cart_items(
    current_user: AuthenticatedUser = Depends(require_scope("customer")),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    service = CartService(db=cast(DatabaseSessionProtocol, db))
    cart = await service.get_cart(user_id=current_user.id)
    return CartResponse(data=cart)  # type: ignore[arg-type]


@router.post("/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    payload: CartItemCreateRequest,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    service = CartService(db=cast(DatabaseSessionProtocol, db))
    try:
        cart = await service.add_item(
            user_id=current_user.id,
            product_variant_id=payload.product_variant_id,
            quantity=payload.quantity,
        )
    except InsufficientStockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CartResponse(data=cart)  # type: ignore[arg-type]


@router.patch("/items/{item_id}", response_model=CartResponse)
async def update_cart_item(
    item_id: UUID,
    payload: CartItemUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    service = CartService(db=cast(DatabaseSessionProtocol, db))
    try:
        cart = await service.update_item_quantity(
            user_id=current_user.id,
            cart_item_id=item_id,
            quantity=payload.quantity,
        )
    except CartItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InsufficientStockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CartResponse(data=cart)  # type: ignore[arg-type]


@router.delete("/items/{item_id}", response_model=CartResponse)
async def delete_cart_item(
    item_id: UUID,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),
    db: AsyncSession = Depends(get_db),
) -> CartResponse:
    service = CartService(db=cast(DatabaseSessionProtocol, db))
    try:
        cart = await service.remove_item(user_id=current_user.id, cart_item_id=item_id)
    except CartItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CartResponse(data=cart)  # type: ignore[arg-type]
