from __future__ import annotations

# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.brand_portal.auth import BrandPortalContext, require_brand_role
from app.core.database import get_db
from app.schemas.product import (
    AdminProductResponse,
    BrandPortalProductCreateRequest,
    BrandPortalProductsResponse,
    BrandPortalProductUpdateRequest,
    PaginationMeta,
    ProductCreateRequest,
    ProductImageReorderRequest,
    ProductImagesResponse,
    ProductStatusLiteral,
    ProductUpdateRequest,
    ProductVariantCreateRequest,
    ProductVariantResponse,
    ProductVariantsResponse,
    ProductVariantUpdateRequest,
)
from app.services.cache_service import CacheService
from app.services.product_image_upload_service import upload_product_images_atomically
from app.services.product_service import ProductService
from app.services.storage_service import MAX_IMAGES_PER_PRODUCT, StorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brand-portal/products", tags=["brand-portal:products"])


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


async def _ensure_owned_product(
    *,
    service: ProductService,
    product_id: UUID,
    context: BrandPortalContext,
) -> None:
    try:
        await service.get_product_by_id_for_brand(
            product_id=product_id,
            brand_id=context.brand_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        ) from exc


def _to_product_create_request(
    *,
    payload: BrandPortalProductCreateRequest,
    brand_id: UUID,
) -> ProductCreateRequest:
    return ProductCreateRequest(brand_id=brand_id, **payload.model_dump())


def _to_product_update_request(payload: BrandPortalProductUpdateRequest) -> ProductUpdateRequest:
    return ProductUpdateRequest(**payload.model_dump(exclude_unset=True))


def _parse_int_list_field(
    *, raw_value: str | None, field_name: str, expected_len: int
) -> list[int]:
    if raw_value is None:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be valid JSON array.",
        ) from exc
    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be a JSON array.",
        )
    try:
        values = [int(item) for item in parsed]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must contain integers.",
        ) from exc
    if len(values) != expected_len:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} length must match files length.",
        )
    return values


def _parse_optional_str_list_field(
    *,
    raw_value: str | None,
    field_name: str,
    expected_len: int,
) -> list[str | None]:
    values: list[str | None] = [None] * expected_len
    if raw_value is None:
        return values
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be valid JSON array.",
        ) from exc
    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be a JSON array.",
        )
    if len(parsed) != expected_len:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} length must match files length.",
        )
    return [(str(item) if item is not None else None) for item in parsed]


@router.get("", response_model=BrandPortalProductsResponse)
async def list_products(
    product_status: ProductStatusLiteral | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    season: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> BrandPortalProductsResponse:
    service = ProductService(db=db)
    items, total = await service.list_brand_products(
        brand_id=context.brand_id,
        product_status=product_status,
        category=category,
        season=season,
        page=page,
        per_page=per_page,
    )
    return BrandPortalProductsResponse(
        data=items,  # type: ignore[arg-type]
        meta=PaginationMeta(page=page, per_page=per_page, total=total),
    )


@router.post("", response_model=AdminProductResponse, status_code=http_status.HTTP_201_CREATED)
async def create_product(
    payload: BrandPortalProductCreateRequest,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager")),
    db: AsyncSession = Depends(get_db),
) -> AdminProductResponse:
    service = ProductService(db=db)
    try:
        product = await service.create_product(
            payload=_to_product_create_request(payload=payload, brand_id=context.brand_id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await _invalidate_catalog_cache()
    return AdminProductResponse(data=product)  # type: ignore[arg-type]


@router.get("/{product_id}", response_model=AdminProductResponse)
async def get_product(
    product_id: UUID,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> AdminProductResponse:
    service = ProductService(db=db)
    try:
        product = await service.get_product_by_id_for_brand(
            product_id=product_id,
            brand_id=context.brand_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        ) from exc
    return AdminProductResponse(data=product)  # type: ignore[arg-type]


@router.put("/{product_id}", response_model=AdminProductResponse)
@router.patch("/{product_id}", response_model=AdminProductResponse)
async def update_product(
    product_id: UUID,
    payload: BrandPortalProductUpdateRequest,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager")),
    db: AsyncSession = Depends(get_db),
) -> AdminProductResponse:
    service = ProductService(db=db)
    await _ensure_owned_product(service=service, product_id=product_id, context=context)
    try:
        product = await service.update_product(
            product_id=product_id,
            payload=_to_product_update_request(payload),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    await _invalidate_catalog_cache()
    return AdminProductResponse(data=product)  # type: ignore[arg-type]


@router.delete("/{product_id}", response_model=AdminProductResponse)
async def delete_product(
    product_id: UUID,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager")),
    db: AsyncSession = Depends(get_db),
) -> AdminProductResponse:
    service = ProductService(db=db)
    await _ensure_owned_product(service=service, product_id=product_id, context=context)
    try:
        product = await service.archive_product(product_id=product_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    await _invalidate_catalog_cache()
    return AdminProductResponse(data=product)  # type: ignore[arg-type]


@router.get("/{product_id}/variants", response_model=ProductVariantsResponse)
async def list_variants(
    product_id: UUID,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> ProductVariantsResponse:
    service = ProductService(db=db)
    await _ensure_owned_product(service=service, product_id=product_id, context=context)
    variants = await service.list_variants(product_id=product_id)
    return ProductVariantsResponse(data=variants)  # type: ignore[arg-type]


@router.get("/{product_id}/variants/{variant_id}", response_model=ProductVariantResponse)
async def get_variant(
    product_id: UUID,
    variant_id: UUID,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> ProductVariantResponse:
    service = ProductService(db=db)
    await _ensure_owned_product(service=service, product_id=product_id, context=context)
    try:
        variant = await service.get_variant(product_id=product_id, variant_id=variant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ProductVariantResponse(data=variant)  # type: ignore[arg-type]


@router.post(
    "/{product_id}/variants",
    response_model=ProductVariantResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def add_variant(
    product_id: UUID,
    payload: ProductVariantCreateRequest,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager")),
    db: AsyncSession = Depends(get_db),
) -> ProductVariantResponse:
    service = ProductService(db=db)
    await _ensure_owned_product(service=service, product_id=product_id, context=context)
    try:
        variant = await service.add_variant(product_id=product_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    await _invalidate_catalog_cache()
    return ProductVariantResponse(data=variant)  # type: ignore[arg-type]


@router.put("/{product_id}/variants/{variant_id}", response_model=ProductVariantResponse)
@router.patch("/{product_id}/variants/{variant_id}", response_model=ProductVariantResponse)
async def update_variant(
    product_id: UUID,
    variant_id: UUID,
    payload: ProductVariantUpdateRequest,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager")),
    db: AsyncSession = Depends(get_db),
) -> ProductVariantResponse:
    service = ProductService(db=db)
    await _ensure_owned_product(service=service, product_id=product_id, context=context)
    try:
        variant = await service.update_variant(
            product_id=product_id,
            variant_id=variant_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    await _invalidate_catalog_cache()
    return ProductVariantResponse(data=variant)  # type: ignore[arg-type]


@router.delete("/{product_id}/variants/{variant_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_variant(
    product_id: UUID,
    variant_id: UUID,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager")),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = ProductService(db=db)
    await _ensure_owned_product(service=service, product_id=product_id, context=context)
    try:
        await service.delete_variant(product_id=product_id, variant_id=variant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    await _invalidate_catalog_cache()


@router.post(
    "/{product_id}/images",
    response_model=ProductImagesResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def upload_images(
    product_id: UUID,
    files: list[UploadFile] = File(...),
    sort_orders: str | None = Form(default=None),
    alt_texts: str | None = Form(default=None),
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager")),
    db: AsyncSession = Depends(get_db),
) -> ProductImagesResponse:
    if len(files) == 0:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="No files provided.",
        )
    if len(files) > MAX_IMAGES_PER_PRODUCT:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files allowed.",
        )

    parsed_sort_orders = _parse_int_list_field(
        raw_value=sort_orders,
        field_name="sort_orders",
        expected_len=len(files),
    )
    parsed_alt_texts = _parse_optional_str_list_field(
        raw_value=alt_texts,
        field_name="alt_texts",
        expected_len=len(files),
    )

    service = ProductService(db=db)
    await _ensure_owned_product(service=service, product_id=product_id, context=context)

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
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await _invalidate_catalog_cache()
    return ProductImagesResponse(data=uploaded_images)  # type: ignore[arg-type]


@router.delete("/{product_id}/images/{image_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_image(
    product_id: UUID,
    image_id: UUID,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager")),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = ProductService(db=db)
    await _ensure_owned_product(service=service, product_id=product_id, context=context)
    storage = StorageService(db_session=db)
    try:
        image = await service.get_image(product_id=product_id, image_id=image_id)
        await storage.delete(str(image["url"]))
        await service.delete_image(product_id=product_id, image_id=image_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    await _invalidate_catalog_cache()


@router.patch("/{product_id}/images/reorder", response_model=ProductImagesResponse)
async def reorder_images(
    product_id: UUID,
    payload: ProductImageReorderRequest,
    context: BrandPortalContext = Depends(require_brand_role("owner", "manager")),
    db: AsyncSession = Depends(get_db),
) -> ProductImagesResponse:
    service = ProductService(db=db)
    await _ensure_owned_product(service=service, product_id=product_id, context=context)
    try:
        images = await service.reorder_images(product_id=product_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    await _invalidate_catalog_cache()
    return ProductImagesResponse(data=images)  # type: ignore[arg-type]
