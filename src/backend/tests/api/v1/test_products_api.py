from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from decimal import Decimal
from typing import ClassVar
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import products
from app.core.database import get_db
from app.main import app
from app.services.product_service import CatalogFilters


class _FakeCacheService:
    payloads: ClassVar[list[dict[str, object]]] = []
    keys: ClassVar[list[str]] = []

    def hashed_key(self, *, prefix: str, payload: Mapping[str, object]) -> str:
        self.payloads.append(dict(payload))
        key = f"{prefix}:{payload.get('is_sale')!r}"
        self.keys.append(key)
        return key

    async def get_json(self, *, key: str) -> object | None:
        _ = key
        return None

    async def set_json(self, *, key: str, ttl_seconds: int, value: object) -> None:
        _ = key, ttl_seconds, value


class _FakeProductService:
    filters: ClassVar[list[CatalogFilters]] = []
    detail_404_slugs: ClassVar[set[str]] = set()

    def __init__(self, *, db: object) -> None:
        _ = db

    async def list_products(
        self,
        *,
        filters: CatalogFilters,
    ) -> tuple[list[dict[str, object]], int]:
        self.filters.append(filters)
        return [_catalog_product()], 1

    async def get_product_by_slug(self, *, slug: str) -> dict[str, object]:
        if slug in self.detail_404_slugs:
            raise ValueError("Product not found.")
        product = _catalog_product()
        return {
            **product,
            "description": "Tailored jacket",
            "fabric_composition": "70% wool, 30% polyester",
            "care_instructions": "Dry clean only",
            "season": "FW26",
            "base_price_rub": Decimal("15000.00"),
            "sale_price_rub": None,
            "product_status": "active",
            "is_active": True,
            "created_at": "2026-05-13T10:00:00Z",
            "variants": [],
        }


async def _override_db() -> AsyncIterator[object]:
    yield object()


def _catalog_product() -> dict[str, object]:
    product_id = uuid4()
    brand_id = uuid4()
    category_id = uuid4()
    image_id = uuid4()
    return {
        "id": product_id,
        "name": "Structured Jacket",
        "slug": "structured-jacket",
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
        "price_from": Decimal("15000.00"),
        "compare_at_price_from": Decimal("18000.00"),
        "is_new_arrival": False,
        "images": [
            {
                "id": image_id,
                "url": "https://cdn.example/products/jacket.jpg",
                "sort_order": 0,
                "alt_text": "Structured Jacket front",
            }
        ],
        "available_sizes": ["S", "M"],
    }


@pytest.fixture(autouse=True)
def _patch_products(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    _FakeCacheService.payloads = []
    _FakeCacheService.keys = []
    _FakeProductService.filters = []
    _FakeProductService.detail_404_slugs = set()
    app.dependency_overrides[get_db] = _override_db
    monkeypatch.setattr(products, "CacheService", _FakeCacheService)
    monkeypatch.setattr(products, "ProductService", _FakeProductService)
    yield
    app.dependency_overrides.pop(get_db, None)


def test_list_products_wires_sale_query_to_filters_and_cache_key() -> None:
    with TestClient(app) as client:
        omitted_response = client.get("/api/v1/products")
        sale_response = client.get("/api/v1/products?is_sale=true")

    assert omitted_response.status_code == 200
    assert sale_response.status_code == 200
    assert _FakeProductService.filters[0].is_sale is None
    assert _FakeProductService.filters[1].is_sale is True
    assert _FakeCacheService.payloads[0]["is_sale"] is None
    assert _FakeCacheService.payloads[1]["is_sale"] is True
    assert _FakeCacheService.keys[0] != _FakeCacheService.keys[1]


@pytest.mark.parametrize(
    "slug",
    [
        "hidden-jacket",
        "archived-jacket",
        "inactive-jacket",
        "brand-inactive-jacket",
    ],
)
def test_get_product_returns_404_for_non_public_final_state(slug: str) -> None:
    _FakeProductService.detail_404_slugs = {slug}

    with TestClient(app) as client:
        response = client.get(f"/api/v1/products/{slug}")

    assert response.status_code == 404
