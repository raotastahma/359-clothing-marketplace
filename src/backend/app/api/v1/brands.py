from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.product import PaginationMeta, PublicBrandDetailResponse, PublicBrandListResponse
from app.services.cache_service import CacheService
from app.services.product_service import ProductService

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("", response_model=PublicBrandListResponse)
async def list_brands(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PublicBrandListResponse:
    cache = CacheService()
    cache_key = cache.hashed_key(
        prefix="brands:list",
        payload={"page": page, "per_page": per_page},
    )
    cached = await cache.get_json(key=cache_key)
    if isinstance(cached, dict):
        return PublicBrandListResponse.model_validate(cached)

    service = ProductService(db=db)
    items, total = await service.list_public_brands(page=page, per_page=per_page)
    response = PublicBrandListResponse(
        data=items,  # type: ignore[arg-type]
        meta=PaginationMeta(page=page, per_page=per_page, total=total),
    )
    await cache.set_json(key=cache_key, ttl_seconds=1800, value=response.model_dump(mode="json"))
    return response


@router.get("/{slug}", response_model=PublicBrandDetailResponse)
async def get_brand(slug: str, db: AsyncSession = Depends(get_db)) -> PublicBrandDetailResponse:
    cache = CacheService()
    cache_key = f"brands:{slug}"
    cached = await cache.get_json(key=cache_key)
    if isinstance(cached, dict):
        return PublicBrandDetailResponse.model_validate(cached)

    service = ProductService(db=db)
    try:
        payload = await service.get_public_brand_by_slug(slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    response = PublicBrandDetailResponse(data=payload)  # type: ignore[arg-type]
    await cache.set_json(key=cache_key, ttl_seconds=1800, value=response.model_dump(mode="json"))
    return response
