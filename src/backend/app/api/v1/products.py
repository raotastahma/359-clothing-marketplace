from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.product import CatalogProductsResponse, PaginationMeta, ProductDetailResponse
from app.services.cache_service import CacheService
from app.services.product_service import CatalogFilters, ProductService

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=CatalogProductsResponse)
async def list_products(
    brand: str | None = Query(default=None),
    category: str | None = Query(default=None),
    gender: str | None = Query(default=None),
    price_min: Decimal | None = Query(default=None),
    price_max: Decimal | None = Query(default=None),
    size: str | None = Query(default=None),
    is_sale: bool | None = Query(default=None),
    sort: str = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> CatalogProductsResponse:
    normalized_sort = "newest" if sort == "popular" else sort
    if normalized_sort not in {"price_asc", "price_desc", "newest"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sort must be one of: price_asc, price_desc, newest, popular",
        )

    cache = CacheService()
    cache_key = cache.hashed_key(
        prefix="products:list",
        payload={
            "brand": brand,
            "category": category,
            "gender": gender,
            "price_min": price_min,
            "price_max": price_max,
            "size": size,
            "is_sale": is_sale,
            "sort": normalized_sort,
            "page": page,
            "per_page": per_page,
        },
    )
    cached = await cache.get_json(key=cache_key)
    if isinstance(cached, dict):
        return CatalogProductsResponse.model_validate(cached)

    service = ProductService(db=db)
    items, total = await service.list_products(
        filters=CatalogFilters(
            brand=brand,
            category=category,
            gender=gender,
            price_min=price_min,
            price_max=price_max,
            size=size,
            is_sale=is_sale,
            sort=normalized_sort,  # type: ignore[arg-type]
            page=page,
            per_page=per_page,
        )
    )
    response = CatalogProductsResponse(
        data=items,  # type: ignore[arg-type]
        meta=PaginationMeta(page=page, per_page=per_page, total=total),
    )
    await cache.set_json(key=cache_key, ttl_seconds=300, value=response.model_dump(mode="json"))
    return response


@router.get("/search", response_model=CatalogProductsResponse)
async def search_products(
    q: str = Query(min_length=1),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> CatalogProductsResponse:
    cache = CacheService()
    cache_key = cache.hashed_key(
        prefix="products:search",
        payload={"q": q, "page": page, "per_page": per_page},
    )
    cached = await cache.get_json(key=cache_key)
    if isinstance(cached, dict):
        return CatalogProductsResponse.model_validate(cached)

    service = ProductService(db=db)
    items, total = await service.search_products(query=q, page=page, per_page=per_page)
    response = CatalogProductsResponse(
        data=items,  # type: ignore[arg-type]
        meta=PaginationMeta(page=page, per_page=per_page, total=total),
    )
    await cache.set_json(key=cache_key, ttl_seconds=300, value=response.model_dump(mode="json"))
    return response


@router.get("/{slug}", response_model=ProductDetailResponse)
async def get_product(slug: str, db: AsyncSession = Depends(get_db)) -> ProductDetailResponse:
    cache = CacheService()
    cache_key = f"products:{slug}"
    cached = await cache.get_json(key=cache_key)
    if isinstance(cached, dict):
        return ProductDetailResponse.model_validate(cached)

    service = ProductService(db=db)
    try:
        product = await service.get_product_by_slug(slug=slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    response = ProductDetailResponse(data=product)  # type: ignore[arg-type]
    await cache.set_json(key=cache_key, ttl_seconds=300, value=response.model_dump(mode="json"))
    return response
