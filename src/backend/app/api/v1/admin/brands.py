from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_scope
from app.schemas.brand import (
    BrandCreateRequest,
    BrandListResponse,
    BrandResponse,
    BrandUpdateRequest,
    PaginationMeta,
)
from app.services.brand_service import BrandService
from app.services.cache_service import CacheService

router = APIRouter(
    prefix="/admin/brands",
    tags=["admin:brands"],
    dependencies=[Depends(require_scope("admin"))],
)


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    payload: BrandCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> BrandResponse:
    service = BrandService(db=db)
    brand = await service.create_brand(payload=payload)
    cache = CacheService()
    await cache.delete_by_prefix(prefix="brands:")
    await cache.delete_by_prefix(prefix="brands:list")
    return BrandResponse(data=brand)  # type: ignore[arg-type]


@router.get("", response_model=BrandListResponse)
async def list_brands(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> BrandListResponse:
    service = BrandService(db=db)
    items, total = await service.list_brands(page=page, per_page=per_page, is_active=is_active)
    return BrandListResponse(
        data=items,  # type: ignore[arg-type]
        meta=PaginationMeta(page=page, per_page=per_page, total=total),
    )


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> BrandResponse:
    service = BrandService(db=db)
    try:
        brand = await service.get_brand_by_id(brand_id=brand_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BrandResponse(data=brand)  # type: ignore[arg-type]


@router.patch("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: UUID,
    payload: BrandUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> BrandResponse:
    service = BrandService(db=db)
    try:
        brand = await service.update_brand(brand_id=brand_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    cache = CacheService()
    await cache.delete_by_prefix(prefix="brands:")
    await cache.delete_by_prefix(prefix="brands:list")
    await cache.delete_by_prefix(prefix="products:list")
    return BrandResponse(data=brand)  # type: ignore[arg-type]


@router.delete("/{brand_id}", response_model=BrandResponse)
async def delete_brand(
    brand_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> BrandResponse:
    service = BrandService(db=db)
    try:
        brand = await service.deactivate_brand(brand_id=brand_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    cache = CacheService()
    await cache.delete_by_prefix(prefix="brands:")
    await cache.delete_by_prefix(prefix="brands:list")
    await cache.delete_by_prefix(prefix="products:list")
    return BrandResponse(data=brand)  # type: ignore[arg-type]
