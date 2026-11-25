from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from typing import ClassVar
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.api.v1.brand_portal import products as bp_products
from app.api.v1.brand_portal.auth import BrandPortalContext
from app.schemas.product import (
    BrandPortalProductCreateRequest,
    BrandPortalProductUpdateRequest,
    ProductCreateRequest,
    ProductImageReorderItem,
    ProductImageReorderRequest,
    ProductUpdateRequest,
    ProductVariantCreateRequest,
    ProductVariantUpdateRequest,
)


class _FakeDb:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.pending_image_urls: list[str] = []
        self.persisted_image_urls: list[str] = []

    async def commit(self) -> None:
        self.commits += 1
        self.persisted_image_urls.extend(self.pending_image_urls)
        self.pending_image_urls.clear()

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.pending_image_urls.clear()


class _ProductServiceResult:
    def __init__(self, rows: list[Mapping[str, object]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> _ProductServiceResult:
        return self

    def first(self) -> Mapping[str, object] | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Mapping[str, object]]:
        return list(self._rows)


class _ProductServiceDb(AsyncSession):
    def __init__(self, results: list[_ProductServiceResult]) -> None:
        self._results = results
        self.statements: list[str] = []
        self.params: list[object] = []
        self.commits = 0

    async def execute(  # type: ignore[override]
        self,
        statement: object,
        params: object | None = None,
        *args: object,
        **kwargs: object,
    ) -> _ProductServiceResult:
        _ = args, kwargs
        self.statements.append(str(statement))
        self.params.append(params)
        if self._results:
            return self._results.pop(0)
        return _ProductServiceResult()

    async def commit(self) -> None:
        self.commits += 1


def _empty_ownership_checks() -> list[tuple[UUID, UUID]]:
    return []


def _empty_detail_rows() -> list[dict[str, object]]:
    return []


def _empty_added_images() -> list[tuple[UUID, str, int, str | None]]:
    return []


def _empty_uploaded_files() -> list[tuple[str, UUID, int]]:
    return []


def _empty_storage_urls() -> list[str]:
    return []


def _empty_image_delete_events() -> list[str]:
    return []


def _empty_image_upload_events() -> list[str]:
    return []


@dataclass
class _ServiceState:
    brand_id: UUID
    product_id: UUID
    owned_missing: bool = False
    image_count: int = 0
    ownership_checks: list[tuple[UUID, UUID]] = field(default_factory=_empty_ownership_checks)
    create_payload: ProductCreateRequest | None = None
    update_payload: ProductUpdateRequest | None = None
    archived_product_id: UUID | None = None
    variant_id: UUID = field(default_factory=uuid4)
    variant_missing: bool = False
    variants: list[dict[str, object]] = field(default_factory=_empty_detail_rows)
    added_variant_payload: ProductVariantCreateRequest | None = None
    updated_variant_payload: ProductVariantUpdateRequest | None = None
    deleted_variant_id: UUID | None = None
    image_id: UUID = field(default_factory=uuid4)
    image_missing: bool = False
    images: list[dict[str, object]] = field(default_factory=_empty_detail_rows)
    added_images: list[tuple[UUID, str, int, str | None]] = field(
        default_factory=_empty_added_images
    )
    deleted_image_id: UUID | None = None
    reordered_payload: ProductImageReorderRequest | None = None
    uploaded_files: list[tuple[str, UUID, int]] = field(default_factory=_empty_uploaded_files)
    upload_failure_at: int | None = None
    deleted_storage_urls: list[str] = field(default_factory=_empty_storage_urls)
    storage_delete_failure: bool = False
    image_delete_events: list[str] = field(default_factory=_empty_image_delete_events)
    image_upload_events: list[str] = field(default_factory=_empty_image_upload_events)
    cache_invalidations: int = 0


class _FakeProductService:
    state: ClassVar[_ServiceState]

    def __init__(self, *, db: object) -> None:
        self._db = db

    async def create_product(self, *, payload: ProductCreateRequest) -> dict[str, object]:
        self.state.create_payload = payload
        return _product_detail(brand_id=payload.brand_id, product_id=self.state.product_id)

    async def get_product_by_id_for_brand(
        self,
        *,
        product_id: UUID,
        brand_id: UUID,
    ) -> dict[str, object]:
        self.state.ownership_checks.append((product_id, brand_id))
        if self.state.owned_missing or brand_id != self.state.brand_id:
            raise ValueError("Product not found.")
        return _product_detail(brand_id=brand_id, product_id=product_id)

    async def update_product(
        self,
        *,
        product_id: UUID,
        payload: ProductUpdateRequest,
    ) -> dict[str, object]:
        self.state.update_payload = payload
        return _product_detail(brand_id=self.state.brand_id, product_id=product_id)

    async def archive_product(self, *, product_id: UUID) -> dict[str, object]:
        self.state.archived_product_id = product_id
        return _product_detail(brand_id=self.state.brand_id, product_id=product_id)

    async def count_images(self, *, product_id: UUID) -> int:
        _ = product_id
        self.state.image_upload_events.append("count")
        return self.state.image_count

    async def lock_product_for_image_upload(self, *, product_id: UUID) -> None:
        _ = product_id
        self.state.image_upload_events.append("lock")

    async def list_variants(self, *, product_id: UUID) -> list[dict[str, object]]:
        _ = product_id
        return self.state.variants

    async def get_variant(self, *, product_id: UUID, variant_id: UUID) -> dict[str, object]:
        _ = product_id
        if self.state.variant_missing:
            raise ValueError("Variant not found.")
        return _variant_detail(variant_id=variant_id)

    async def add_variant(
        self,
        *,
        product_id: UUID,
        payload: ProductVariantCreateRequest,
    ) -> dict[str, object]:
        _ = product_id
        if self.state.variant_missing:
            raise ValueError("Product not found.")
        self.state.added_variant_payload = payload
        return _variant_detail(variant_id=self.state.variant_id, size=payload.size)

    async def update_variant(
        self,
        *,
        product_id: UUID,
        variant_id: UUID,
        payload: ProductVariantUpdateRequest,
    ) -> dict[str, object]:
        _ = product_id
        if self.state.variant_missing:
            raise ValueError("Variant not found.")
        self.state.updated_variant_payload = payload
        return _variant_detail(variant_id=variant_id, size=payload.size or "S")

    async def delete_variant(self, *, product_id: UUID, variant_id: UUID) -> None:
        _ = product_id
        if self.state.variant_missing:
            raise ValueError("Variant not found.")
        self.state.deleted_variant_id = variant_id

    async def add_image(
        self,
        *,
        product_id: UUID,
        url: str,
        sort_order: int,
        alt_text: str | None,
        commit: bool = True,
    ) -> dict[str, object]:
        self.state.added_images.append((product_id, url, sort_order, alt_text))
        if isinstance(self._db, _FakeDb):
            self._db.pending_image_urls.append(url)
            if commit:
                await self._db.commit()
        return _image_detail(
            image_id=self.state.image_id, url=url, sort_order=sort_order, alt_text=alt_text
        )

    async def delete_image(self, *, product_id: UUID, image_id: UUID) -> str:
        _ = product_id
        if self.state.image_missing:
            raise ValueError("Image not found.")
        self.state.image_delete_events.append("db-delete")
        self.state.deleted_image_id = image_id
        return "https://cdn.example/products/image.jpg"

    async def get_image(self, *, product_id: UUID, image_id: UUID) -> dict[str, object]:
        _ = product_id
        self.state.image_delete_events.append("db-read")
        if self.state.image_missing:
            raise ValueError("Image not found.")
        return _image_detail(image_id=image_id)

    async def reorder_images(
        self,
        *,
        product_id: UUID,
        payload: ProductImageReorderRequest,
    ) -> list[dict[str, object]]:
        _ = product_id
        if self.state.image_missing:
            raise ValueError("Image not found.")
        self.state.reordered_payload = payload
        return [
            _image_detail(
                image_id=item.image_id,
                url=f"https://cdn.example/products/{item.image_id}.jpg",
                sort_order=item.sort_order,
                alt_text=None,
            )
            for item in payload.items
        ]


class _FakeStorageService:
    state: ClassVar[_ServiceState]

    def __init__(self, *, db_session: object) -> None:
        _ = db_session

    async def upload(self, file: UploadFile, product_id: UUID, sort_order: int) -> str:
        if self.state.upload_failure_at == len(self.state.uploaded_files):
            raise ValueError("Upload failed.")
        filename = file.filename or "image.jpg"
        self.state.uploaded_files.append((filename, product_id, sort_order))
        return f"https://cdn.example/products/{product_id}/{sort_order}-{filename}"

    async def delete(self, url_or_key: str) -> None:
        self.state.image_delete_events.append("storage-delete")
        if self.state.storage_delete_failure:
            raise RuntimeError("Storage delete failed.")
        self.state.deleted_storage_urls.append(url_or_key)


class _FakeCacheService:
    prefixes: ClassVar[list[str]]
    failure_prefix: ClassVar[str | None]

    async def delete_by_prefix(self, *, prefix: str) -> None:
        self.prefixes.append(prefix)
        if prefix == self.failure_prefix:
            raise RuntimeError("Redis unavailable.")


def _product_detail(*, brand_id: UUID, product_id: UUID) -> dict[str, object]:
    category_id = uuid4()
    return {
        "id": product_id,
        "name": "Structured Jacket",
        "slug": "structured-jacket",
        "description": "Tailored jacket",
        "fabric_composition": "70% wool, 30% polyester",
        "care_instructions": "Dry clean only",
        "season": "FW26",
        "base_price_rub": Decimal("15000.00"),
        "sale_price_rub": None,
        "product_status": "active",
        "is_active": True,
        "is_new_arrival": False,
        "created_at": datetime(2026, 5, 13, tzinfo=UTC),
        "brand": {
            "id": brand_id,
            "name": "MASLOV",
            "slug": "maslov",
            "logo_url": None,
        },
        "category": {
            "id": category_id,
            "name": "Jackets",
            "slug": "jackets",
            "gender": "unisex",
            "parent": None,
        },
        "variants": [],
        "images": [],
    }


def _product_service_row(*, brand_id: UUID, product_id: UUID) -> dict[str, object]:
    category_id = uuid4()
    return {
        "id": product_id,
        "name": "Structured Jacket",
        "slug": "structured-jacket",
        "description": None,
        "fabric_composition": None,
        "care_instructions": None,
        "season": None,
        "base_price_rub": Decimal("15000.00"),
        "sale_price_rub": None,
        "product_status": "active",
        "is_active": True,
        "is_new_arrival": False,
        "created_at": datetime.now(UTC),
        "brand_id": brand_id,
        "brand_name": "MASLOV",
        "brand_slug": "maslov",
        "brand_logo_url": None,
        "category_id": category_id,
        "category_name": "Jackets",
        "category_slug": "jackets",
        "category_gender": "unisex",
        "parent_name": None,
        "parent_slug": None,
    }


def _variant_detail(*, variant_id: UUID, size: str = "S") -> dict[str, object]:
    return {
        "id": variant_id,
        "vendor_code": "MSL-JKT-001-S",
        "size": size,
        "color": None,
        "sku": f"MSL-JKT-001-{size}",
        "price_rub": Decimal("15000.00"),
        "compare_at_price_rub": None,
        "stock_quantity": 5,
        "is_active": True,
    }


def _image_detail(
    *,
    image_id: UUID,
    url: str = "https://cdn.example/products/image.jpg",
    sort_order: int = 0,
    alt_text: str | None = None,
) -> dict[str, object]:
    return {
        "id": image_id,
        "url": url,
        "sort_order": sort_order,
        "alt_text": alt_text,
    }


def _context(*, brand_id: UUID) -> BrandPortalContext:
    return BrandPortalContext(
        user_id=uuid4(),
        brand_id=brand_id,
        brand_name="MASLOV",
        brand_slug="maslov",
        brand_logo_url=None,
        commission_rate=Decimal("0.3500"),
        role="manager",
    )


def _install_service(monkeypatch: pytest.MonkeyPatch, state: _ServiceState) -> None:
    _FakeProductService.state = state
    _FakeStorageService.state = state
    monkeypatch.setattr(bp_products, "ProductService", _FakeProductService)
    monkeypatch.setattr(bp_products, "StorageService", _FakeStorageService)

    async def _track_invalidate() -> None:
        state.cache_invalidations += 1

    monkeypatch.setattr(bp_products, "_invalidate_catalog_cache", _track_invalidate)


def _upload_file(*, filename: str = "photo.jpg") -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(b"fake-jpeg"),
        headers=Headers({"content-type": "image/jpeg"}),
    )


def _create_payload() -> BrandPortalProductCreateRequest:
    return BrandPortalProductCreateRequest(
        name="Structured Jacket",
        category_id=uuid4(),
        base_price_rub=Decimal("15000.00"),
        variants=[
            ProductVariantCreateRequest(
                vendor_code="MSL-JKT-001-S",
                size="S",
                sku="MSL-JKT-001-S",
                price_rub=Decimal("15000.00"),
                stock_quantity=5,
            )
        ],
    )


@pytest.mark.asyncio
async def test_catalog_cache_invalidation_deletes_documented_public_prefixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeCacheService.prefixes = []
    _FakeCacheService.failure_prefix = None
    monkeypatch.setattr(bp_products, "CacheService", _FakeCacheService)

    await bp_products._invalidate_catalog_cache()

    assert _FakeCacheService.prefixes == [
        "products:",
        "products:list",
        "products:search",
        "brands:",
        "brands:list",
        "categories:tree",
    ]


def test_brand_portal_create_rejects_body_brand_id() -> None:
    with pytest.raises(ValidationError):
        BrandPortalProductCreateRequest.model_validate(
            {
                "name": "Structured Jacket",
                "brand_id": str(uuid4()),
                "category_id": str(uuid4()),
                "variants": [
                    {
                        "size": "S",
                        "sku": "MSL-JKT-001-S",
                        "price_rub": "15000.00",
                    }
                ],
            }
        )


@pytest.mark.asyncio
async def test_create_product_uses_authenticated_brand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=uuid4())
    _install_service(monkeypatch, state)

    response = await bp_products.create_product(
        _create_payload(),
        context=_context(brand_id=brand_id),
        db=_FakeDb(),  # type: ignore[arg-type]
    )

    assert response.data.brand.id == brand_id
    assert state.create_payload is not None
    assert state.create_payload.brand_id == brand_id
    assert state.cache_invalidations == 1


@pytest.mark.asyncio
async def test_create_product_returns_success_when_cache_invalidation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_invalidate = bp_products._invalidate_catalog_cache
    brand_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=uuid4())
    _install_service(monkeypatch, state)
    _FakeCacheService.prefixes = []
    _FakeCacheService.failure_prefix = "products:list"
    monkeypatch.setattr(bp_products, "CacheService", _FakeCacheService)
    monkeypatch.setattr(bp_products, "_invalidate_catalog_cache", real_invalidate)

    response = await bp_products.create_product(
        _create_payload(),
        context=_context(brand_id=brand_id),
        db=_FakeDb(),  # type: ignore[arg-type]
    )

    assert response.data.id == state.product_id
    assert _FakeCacheService.prefixes == [
        "products:",
        "products:list",
        "products:search",
        "brands:",
        "brands:list",
        "categories:tree",
    ]


@pytest.mark.asyncio
async def test_get_product_raises_404_when_product_is_not_brand_owned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id, owned_missing=True)
    _install_service(monkeypatch, state)

    with pytest.raises(HTTPException) as exc_info:
        await bp_products.get_product(
            product_id,
            context=_context(brand_id=brand_id),
            db=_FakeDb(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404
    assert state.ownership_checks == [(product_id, brand_id)]


@pytest.mark.asyncio
async def test_update_product_checks_brand_ownership_before_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id)
    _install_service(monkeypatch, state)

    await bp_products.update_product(
        product_id,
        BrandPortalProductUpdateRequest(name="Updated Jacket"),
        context=_context(brand_id=brand_id),
        db=_FakeDb(),  # type: ignore[arg-type]
    )

    assert state.ownership_checks == [(product_id, brand_id)]
    assert state.update_payload is not None
    assert state.update_payload.model_dump(exclude_unset=True) == {"name": "Updated Jacket"}
    assert state.cache_invalidations == 1


@pytest.mark.asyncio
async def test_delete_product_archives_only_after_brand_ownership_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id)
    _install_service(monkeypatch, state)

    await bp_products.delete_product(
        product_id,
        context=_context(brand_id=brand_id),
        db=_FakeDb(),  # type: ignore[arg-type]
    )

    assert state.ownership_checks == [(product_id, brand_id)]
    assert state.archived_product_id == product_id
    assert state.cache_invalidations == 1


@pytest.mark.asyncio
async def test_list_variants_returns_owned_product_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    variant_id = uuid4()
    state = _ServiceState(
        brand_id=brand_id,
        product_id=product_id,
        variants=[_variant_detail(variant_id=variant_id)],
    )
    _install_service(monkeypatch, state)

    response = await bp_products.list_variants(
        product_id,
        context=_context(brand_id=brand_id),
        db=_FakeDb(),  # type: ignore[arg-type]
    )

    assert state.ownership_checks == [(product_id, brand_id)]
    assert [variant.id for variant in response.data] == [variant_id]


@pytest.mark.asyncio
async def test_get_variant_raises_404_when_variant_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    variant_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id, variant_missing=True)
    _install_service(monkeypatch, state)

    with pytest.raises(HTTPException) as exc_info:
        await bp_products.get_variant(
            product_id,
            variant_id,
            context=_context(brand_id=brand_id),
            db=_FakeDb(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404
    assert state.ownership_checks == [(product_id, brand_id)]


@pytest.mark.asyncio
async def test_add_variant_checks_brand_ownership_before_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    variant_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id, variant_id=variant_id)
    _install_service(monkeypatch, state)
    payload = ProductVariantCreateRequest(
        vendor_code="MSL-JKT-001-M",
        size="M",
        sku="MSL-JKT-001-M",
        price_rub=Decimal("15000.00"),
        stock_quantity=4,
    )

    response = await bp_products.add_variant(
        product_id,
        payload,
        context=_context(brand_id=brand_id),
        db=_FakeDb(),  # type: ignore[arg-type]
    )

    assert state.ownership_checks == [(product_id, brand_id)]
    assert state.added_variant_payload == payload
    assert response.data.id == variant_id
    assert response.data.size == "M"
    assert state.cache_invalidations == 1


@pytest.mark.asyncio
async def test_add_variant_raises_404_when_service_rejects_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id, variant_missing=True)
    _install_service(monkeypatch, state)

    with pytest.raises(HTTPException) as exc_info:
        await bp_products.add_variant(
            product_id,
            ProductVariantCreateRequest(
                size="M",
                sku="MSL-JKT-001-M",
                price_rub=Decimal("15000.00"),
            ),
            context=_context(brand_id=brand_id),
            db=_FakeDb(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_variant_checks_brand_ownership_before_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    variant_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id)
    _install_service(monkeypatch, state)
    payload = ProductVariantUpdateRequest(size="L", stock_quantity=2)

    response = await bp_products.update_variant(
        product_id,
        variant_id,
        payload,
        context=_context(brand_id=brand_id),
        db=_FakeDb(),  # type: ignore[arg-type]
    )

    assert state.ownership_checks == [(product_id, brand_id)]
    assert state.updated_variant_payload == payload
    assert response.data.id == variant_id
    assert response.data.size == "L"
    assert state.cache_invalidations == 1


@pytest.mark.asyncio
async def test_update_variant_raises_404_when_variant_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    variant_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id, variant_missing=True)
    _install_service(monkeypatch, state)

    with pytest.raises(HTTPException) as exc_info:
        await bp_products.update_variant(
            product_id,
            variant_id,
            ProductVariantUpdateRequest(size="L"),
            context=_context(brand_id=brand_id),
            db=_FakeDb(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_variant_checks_brand_ownership_before_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    variant_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id)
    _install_service(monkeypatch, state)

    await bp_products.delete_variant(
        product_id,
        variant_id,
        context=_context(brand_id=brand_id),
        db=_FakeDb(),  # type: ignore[arg-type]
    )

    assert state.ownership_checks == [(product_id, brand_id)]
    assert state.deleted_variant_id == variant_id
    assert state.cache_invalidations == 1


@pytest.mark.asyncio
async def test_delete_variant_raises_404_when_variant_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    variant_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id, variant_missing=True)
    _install_service(monkeypatch, state)

    with pytest.raises(HTTPException) as exc_info:
        await bp_products.delete_variant(
            product_id,
            variant_id,
            context=_context(brand_id=brand_id),
            db=_FakeDb(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_upload_images_stores_public_urls_for_owned_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    image_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id, image_id=image_id)
    _install_service(monkeypatch, state)

    response = await bp_products.upload_images(
        product_id,
        files=[_upload_file()],
        sort_orders="[3]",
        alt_texts='["Front"]',
        context=_context(brand_id=brand_id),
        db=_FakeDb(),  # type: ignore[arg-type]
    )

    expected_url = f"https://cdn.example/products/{product_id}/3-photo.jpg"
    assert state.ownership_checks == [(product_id, brand_id)]
    assert state.uploaded_files == [("photo.jpg", product_id, 3)]
    assert state.added_images == [(product_id, expected_url, 3, "Front")]
    assert response.data[0].id == image_id
    assert response.data[0].url == expected_url
    assert state.cache_invalidations == 1


@pytest.mark.asyncio
async def test_upload_images_commits_successful_batch_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id)
    _install_service(monkeypatch, state)
    db = _FakeDb()

    response = await bp_products.upload_images(
        product_id,
        files=[_upload_file(filename="front.jpg"), _upload_file(filename="back.jpg")],
        sort_orders=None,
        alt_texts=None,
        context=_context(brand_id=brand_id),
        db=db,  # type: ignore[arg-type]
    )

    expected_urls = [
        f"https://cdn.example/products/{product_id}/0-front.jpg",
        f"https://cdn.example/products/{product_id}/1-back.jpg",
    ]
    assert db.commits == 1
    assert db.rollbacks == 0
    assert db.pending_image_urls == []
    assert db.persisted_image_urls == expected_urls
    assert [str(image.url) for image in response.data] == expected_urls


@pytest.mark.asyncio
async def test_upload_images_rolls_back_and_cleans_storage_when_later_file_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    state = _ServiceState(
        brand_id=brand_id,
        product_id=product_id,
        upload_failure_at=1,
    )
    _install_service(monkeypatch, state)
    db = _FakeDb()

    with pytest.raises(HTTPException) as exc_info:
        await bp_products.upload_images(
            product_id,
            files=[_upload_file(filename="front.jpg"), _upload_file(filename="back.jpg")],
            sort_orders=None,
            alt_texts=None,
            context=_context(brand_id=brand_id),
            db=db,  # type: ignore[arg-type]
        )

    first_url = f"https://cdn.example/products/{product_id}/0-front.jpg"
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Upload failed."
    assert db.commits == 0
    assert db.rollbacks == 1
    assert db.pending_image_urls == []
    assert db.persisted_image_urls == []
    assert state.deleted_storage_urls == [first_url]
    assert state.cache_invalidations == 0


@pytest.mark.asyncio
async def test_upload_images_rejects_when_product_would_exceed_ten_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id, image_count=9)
    _install_service(monkeypatch, state)

    with pytest.raises(HTTPException) as exc_info:
        await bp_products.upload_images(
            product_id,
            files=[_upload_file(), _upload_file()],
            sort_orders=None,
            alt_texts=None,
            context=_context(brand_id=brand_id),
            db=_FakeDb(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "A product cannot have more than 10 images."
    assert state.uploaded_files == []
    assert state.image_upload_events == ["lock", "count"]


@pytest.mark.asyncio
async def test_upload_images_rejects_mismatched_sort_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id)
    _install_service(monkeypatch, state)

    with pytest.raises(HTTPException) as exc_info:
        await bp_products.upload_images(
            product_id,
            files=[_upload_file(), _upload_file()],
            sort_orders="[0]",
            alt_texts=None,
            context=_context(brand_id=brand_id),
            db=_FakeDb(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "sort_orders length must match files length."
    assert state.ownership_checks == []


@pytest.mark.asyncio
async def test_delete_image_removes_storage_object_for_owned_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    image_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id)
    _install_service(monkeypatch, state)

    await bp_products.delete_image(
        product_id,
        image_id,
        context=_context(brand_id=brand_id),
        db=_FakeDb(),  # type: ignore[arg-type]
    )

    assert state.ownership_checks == [(product_id, brand_id)]
    assert state.deleted_image_id == image_id
    assert state.deleted_storage_urls == ["https://cdn.example/products/image.jpg"]
    assert state.image_delete_events == ["db-read", "storage-delete", "db-delete"]
    assert state.cache_invalidations == 1


@pytest.mark.asyncio
async def test_delete_image_keeps_database_row_when_storage_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    image_id = uuid4()
    state = _ServiceState(
        brand_id=brand_id,
        product_id=product_id,
        storage_delete_failure=True,
    )
    _install_service(monkeypatch, state)

    with pytest.raises(RuntimeError, match="Storage delete failed"):
        await bp_products.delete_image(
            product_id,
            image_id,
            context=_context(brand_id=brand_id),
            db=_FakeDb(),  # type: ignore[arg-type]
        )

    assert state.image_delete_events == ["db-read", "storage-delete"]
    assert state.deleted_image_id is None
    assert state.deleted_storage_urls == []
    assert state.cache_invalidations == 0


@pytest.mark.asyncio
async def test_delete_image_raises_404_when_image_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    image_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id, image_missing=True)
    _install_service(monkeypatch, state)

    with pytest.raises(HTTPException) as exc_info:
        await bp_products.delete_image(
            product_id,
            image_id,
            context=_context(brand_id=brand_id),
            db=_FakeDb(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404
    assert state.deleted_storage_urls == []


@pytest.mark.asyncio
async def test_reorder_images_updates_owned_product_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand_id = uuid4()
    product_id = uuid4()
    first_image_id = uuid4()
    second_image_id = uuid4()
    state = _ServiceState(brand_id=brand_id, product_id=product_id)
    _install_service(monkeypatch, state)
    payload = ProductImageReorderRequest(
        items=[
            ProductImageReorderItem(image_id=first_image_id, sort_order=1),
            ProductImageReorderItem(image_id=second_image_id, sort_order=0),
        ]
    )

    response = await bp_products.reorder_images(
        product_id,
        payload,
        context=_context(brand_id=brand_id),
        db=_FakeDb(),  # type: ignore[arg-type]
    )

    assert state.ownership_checks == [(product_id, brand_id)]
    assert state.reordered_payload == payload
    assert [image.id for image in response.data] == [first_image_id, second_image_id]
    assert [image.sort_order for image in response.data] == [1, 0]
    assert state.cache_invalidations == 1


@pytest.mark.asyncio
async def test_reorder_images_raises_404_when_image_is_missing() -> None:
    brand_id = uuid4()
    product_id = uuid4()
    image_id = uuid4()
    db = _ProductServiceDb(
        [
            _ProductServiceResult([_product_service_row(brand_id=brand_id, product_id=product_id)]),
            _ProductServiceResult(),
            _ProductServiceResult(),
            _ProductServiceResult(),
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        await bp_products.reorder_images(
            product_id,
            ProductImageReorderRequest(
                items=[ProductImageReorderItem(image_id=image_id, sort_order=0)]
            ),
            context=_context(brand_id=brand_id),
            db=db,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Image not found."
    assert db.commits == 0
    assert "UPDATE product_images" in db.statements[3]
    assert "RETURNING id" in db.statements[3]
