from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.product import CategoriesTreeResponse
from app.services.cache_service import CacheService
from app.services.product_service import ProductService

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoriesTreeResponse)
async def get_categories_tree(db: AsyncSession = Depends(get_db)) -> CategoriesTreeResponse:
    cache = CacheService()
    cache_key = "categories:tree"
    cached = await cache.get_json(key=cache_key)
    if isinstance(cached, dict):
        return CategoriesTreeResponse.model_validate(cached)

    service = ProductService(db=db)
    tree = await service.get_categories_tree()
    response = CategoriesTreeResponse(data=tree)  # type: ignore[arg-type]
    await cache.set_json(key=cache_key, ttl_seconds=3600, value=response.model_dump(mode="json"))
    return response
