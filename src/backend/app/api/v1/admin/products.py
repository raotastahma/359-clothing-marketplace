from __future__ import annotations

# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_scope
from app.schemas.product import (
    AdminProductResponse,
    ProductCreateRequest,
    ProductImageReorderRequest,
    ProductImagesResponse,
    ProductUpdateRequest,
    ProductVariantCreateRequest,
    ProductVariantResponse,
    ProductVariantUpdateRequest,
)
from app.services.cache_service import CacheService
from app.services.product_image_upload_service import upload_product_images_atomically
from app.services.product_service import ProductService
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/products",
    tags=["admin:products"],
    dependencies=[Depends(require_scope("admin"))],
)


async def _invalidate_catalog_cache() -> None:
    cache = CacheService()
    for prefix in (
        "products:",
        "products:list",
        "products:search",
        "brands:",
        "brands:list",
        "categories:tree",
    ):
        try:
            await cache.delete_by_prefix(prefix=prefix)
        except Exception:
            logger.exception("Catalog cache invalidation failed for prefix %s.", prefix)


@router.post("", response_model=AdminProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> AdminProductResponse:
    service = ProductService(db=db)
    try:
        product = await service.create_product(payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await _invalidate_catalog_cache()
    return AdminProductResponse(data=product)  # type: ignore[arg-type]


@router.patch("/{product_id}", response_model=AdminProductResponse)
async def update_product(
    product_id: UUID,
    payload: ProductUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> AdminProductResponse:
    service = ProductService(db=db)
    try:
        product = await service.update_product(product_id=product_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await _invalidate_catalog_cache()
    return AdminProductResponse(data=product)  # type: ignore[arg-type]


@router.delete("/{product_id}", response_model=AdminProductResponse)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AdminProductResponse:
    service = ProductService(db=db)
    try:
        product = await service.archive_product(product_id=product_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await _invalidate_catalog_cache()
    return AdminProductResponse(data=product)  # type: ignore[arg-type]


@router.post("/{product_id}/variants", response_model=ProductVariantResponse, status_code=201)
async def add_variant(
    product_id: UUID,
    payload: ProductVariantCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ProductVariantResponse:
    service = ProductService(db=db)
    try:
        variant = await service.add_variant(product_id=product_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await _invalidate_catalog_cache()
    return ProductVariantResponse(data=variant)  # type: ignore[arg-type]


@router.patch("/{product_id}/variants/{variant_id}", response_model=ProductVariantResponse)
async def update_variant(
    product_id: UUID,
    variant_id: UUID,
    payload: ProductVariantUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ProductVariantResponse:
    service = ProductService(db=db)
    try:
        variant = await service.update_variant(
            product_id=product_id,
            variant_id=variant_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await _invalidate_catalog_cache()
    return ProductVariantResponse(data=variant)  # type: ignore[arg-type]


@router.delete("/{product_id}/variants/{variant_id}", status_code=204)
async def delete_variant(
    product_id: UUID,
    variant_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    service = ProductService(db=db)
    try:
        await service.delete_variant(product_id=product_id, variant_id=variant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await _invalidate_catalog_cache()


@router.post("/{product_id}/images", response_model=ProductImagesResponse, status_code=201)
async def upload_images(
    product_id: UUID,
    files: list[UploadFile] = File(...),
    sort_orders: str | None = Form(default=None),
    alt_texts: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> ProductImagesResponse:
    if len(files) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided.")
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files allowed.",
        )

    parsed_sort_orders: list[int] = []
    if sort_orders is not None:
        try:
            sort_json = json.loads(sort_orders)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="sort_orders must be valid JSON array.",
            ) from exc
        if not isinstance(sort_json, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="sort_orders must be a JSON array.",
            )
        parsed_sort_orders = [int(item) for item in sort_json]
        if len(parsed_sort_orders) != len(files):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="sort_orders length must match files length.",
            )

    parsed_alt_texts: list[str | None] = [None] * len(files)
    if alt_texts is not None:
        try:
            alt_json = json.loads(alt_texts)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="alt_texts must be valid JSON array.",
            ) from exc
        if not isinstance(alt_json, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="alt_texts must be a JSON array.",
            )
        if len(alt_json) != len(files):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="alt_texts length must match files length.",
            )
        parsed_alt_texts = [(str(item) if item is not None else None) for item in alt_json]

    service = ProductService(db=db)
    storage = StorageService(db_session=db)
    try:
        uploaded_images = await upload_product_images_atomically(
            db=db,
            product_service=service,
            storage=storage,
            product_id=product_id,
            files=files,
            sort_orders=parsed_sort_orders,
            alt_texts=parsed_alt_texts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await _invalidate_catalog_cache()
    return ProductImagesResponse(data=uploaded_images)  # type: ignore[arg-type]


@router.delete("/{product_id}/images/{image_id}", status_code=204)
async def delete_image(
    product_id: UUID,
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    service = ProductService(db=db)
    storage = StorageService(db_session=db)
    try:
        image = await service.get_image(product_id=product_id, image_id=image_id)
        await storage.delete(str(image["url"]))
        await service.delete_image(product_id=product_id, image_id=image_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await _invalidate_catalog_cache()


@router.patch("/{product_id}/images/reorder", response_model=ProductImagesResponse)
async def reorder_images(
    product_id: UUID,
    payload: ProductImageReorderRequest,
    db: AsyncSession = Depends(get_db),
) -> ProductImagesResponse:
    service = ProductService(db=db)
    try:
        images = await service.reorder_images(product_id=product_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await _invalidate_catalog_cache()
    return ProductImagesResponse(data=images)  # type: ignore[arg-type]
