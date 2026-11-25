from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.product_service import CatalogFilters, ProductService


class _CatalogResult:
    def __init__(self, rows: list[Mapping[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> _CatalogResult:
        return self

    def all(self) -> list[Mapping[str, object]]:
        return self._rows

    def first(self) -> Mapping[str, object] | None:
        if not self._rows:
            return None
        return self._rows[0]


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _CatalogDb(AsyncSession):
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[Mapping[str, object] | None] = []

    async def execute(  # type: ignore[override]
        self,
        statement: sa.TextClause,
        params: Mapping[str, object] | None = None,
    ) -> _CatalogResult:
        self.statements.append(str(statement))
        self.params.append(params)
        if len(self.statements) == 1:
            return _CatalogResult([])
        return _CatalogResult([{"total": 0}])


class _SlugDb(AsyncSession):
    def __init__(self, values: list[object | None]) -> None:
        self._values = values
        self.statements: list[str] = []
        self.params: list[Mapping[str, object] | None] = []

    async def execute(  # type: ignore[override]
        self,
        statement: sa.TextClause,
        params: Mapping[str, object] | None = None,
    ) -> _ScalarResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return _ScalarResult(self._values.pop(0))


class _ImageDb(AsyncSession):
    def __init__(self) -> None:
        self.calls = 0
        self.commits = 0
        self.image_id = uuid4()

    async def execute(  # type: ignore[override]
        self,
        statement: sa.TextClause,
        params: Mapping[str, object] | None = None,
    ) -> _ScalarResult | _CatalogResult:
        _ = statement, params
        self.calls += 1
        if self.calls == 1:
            return _ScalarResult(1)
        return _CatalogResult(
            [
                {
                    "id": self.image_id,
                    "url": "https://cdn.example/image.jpg",
                    "sort_order": 0,
                    "alt_text": None,
                }
            ]
        )

    async def commit(self) -> None:
        self.commits += 1


class _ProductLockDb(AsyncSession):
    def __init__(self, *, product_id: object) -> None:
        self.product_id = product_id
        self.statements: list[str] = []
        self.params: list[Mapping[str, object] | None] = []

    async def execute(  # type: ignore[override]
        self,
        statement: sa.TextClause,
        params: Mapping[str, object] | None = None,
    ) -> _CatalogResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return _CatalogResult([{"id": self.product_id}])


def _normalize_sql(statement: str) -> str:
    return " ".join(statement.split())


def _catalog_filters() -> CatalogFilters:
    return CatalogFilters(
        brand=None,
        category=None,
        gender=None,
        price_min=None,
        price_max=None,
        size=None,
        is_sale=None,
        sort="newest",
        page=1,
        per_page=20,
    )


@pytest.mark.asyncio
async def test_list_products_category_filter_includes_descendants() -> None:
    db = _CatalogDb()
    service = ProductService(db=db)

    items, total = await service.list_products(
        filters=CatalogFilters(
            brand=None,
            category="men-clothing",
            gender=None,
            price_min=None,
            price_max=None,
            size=None,
            is_sale=None,
            sort="newest",
            page=1,
            per_page=20,
        )
    )

    assert items == []
    assert total == 0
    assert len(db.statements) == 2
    assert db.params[0] is not None
    assert db.params[0]["category_slug"] == "men-clothing"
    category_predicate = (
        "WITH RECURSIVE category_scope AS ( SELECT id FROM categories "
        "WHERE slug = CAST(:category_slug AS text) UNION ALL SELECT child.id "
        "FROM categories child JOIN category_scope parent ON child.parent_id = parent.id ) "
        "SELECT id FROM category_scope"
    )
    assert category_predicate in _normalize_sql(db.statements[0])
    assert category_predicate in _normalize_sql(db.statements[1])


@pytest.mark.asyncio
async def test_list_products_uses_comma_separated_size_filter() -> None:
    db = _CatalogDb()
    service = ProductService(db=db)

    items, total = await service.list_products(
        filters=CatalogFilters(
            brand=None,
            category=None,
            gender=None,
            price_min=None,
            price_max=None,
            size="S,M",
            is_sale=None,
            sort="newest",
            page=1,
            per_page=20,
        )
    )

    assert items == []
    assert total == 0
    assert len(db.statements) == 2
    assert db.params[0] is not None
    assert db.params[0]["size_filter"] == "S,M"
    size_predicate = "sv.size = ANY(string_to_array(CAST(:size_filter AS text), ','))"
    assert size_predicate in _normalize_sql(db.statements[0])
    assert size_predicate in _normalize_sql(db.statements[1])


@pytest.mark.asyncio
async def test_list_products_applies_sale_filter_to_items_and_total() -> None:
    db = _CatalogDb()
    service = ProductService(db=db)

    items, total = await service.list_products(
        filters=CatalogFilters(
            brand=None,
            category=None,
            gender=None,
            price_min=None,
            price_max=None,
            size=None,
            is_sale=True,
            sort="newest",
            page=1,
            per_page=20,
        )
    )

    assert items == []
    assert total == 0
    assert len(db.statements) == 2
    assert db.params[0] is not None
    assert db.params[0]["is_sale"] is True
    assert db.params[1] is not None
    assert db.params[1]["is_sale"] is True
    sale_predicate = (
        "sale_v.compare_at_price_rub IS NOT NULL AND sale_v.compare_at_price_rub > sale_v.price_rub"
    )
    assert sale_predicate in _normalize_sql(db.statements[0])
    assert sale_predicate in _normalize_sql(db.statements[1])


@pytest.mark.asyncio
async def test_list_products_requires_final_public_state_for_items_and_total() -> None:
    db = _CatalogDb()
    service = ProductService(db=db)

    items, total = await service.list_products(filters=_catalog_filters())

    assert items == []
    assert total == 0
    item_sql = _normalize_sql(db.statements[0])
    total_sql = _normalize_sql(db.statements[1])
    for statement in (item_sql, total_sql):
        assert "p.is_active = TRUE" in statement
        assert "p.product_status = 'active'" in statement
        assert "b.is_active = TRUE" in statement
    assert "sv.is_active = TRUE AND sv.stock_quantity > 0" in item_sql


@pytest.mark.asyncio
async def test_search_products_requires_final_public_state_for_items_and_total() -> None:
    db = _CatalogDb()
    service = ProductService(db=db)

    items, total = await service.search_products(query="jacket", page=1, per_page=20)

    assert items == []
    assert total == 0
    item_sql = _normalize_sql(db.statements[0])
    total_sql = _normalize_sql(db.statements[1])
    for statement in (item_sql, total_sql):
        assert "p.is_active = TRUE" in statement
        assert "p.product_status = 'active'" in statement
        assert "b.is_active = TRUE" in statement
    assert "sv.is_active = TRUE AND sv.stock_quantity > 0" in item_sql


@pytest.mark.asyncio
async def test_get_product_by_slug_requires_final_public_state() -> None:
    db = _CatalogDb()
    service = ProductService(db=db)

    with pytest.raises(ValueError):
        await service.get_product_by_slug(slug="structured-jacket")

    statement = _normalize_sql(db.statements[0])
    assert "p.slug = :slug" in statement
    assert "p.is_active = TRUE" in statement
    assert "p.product_status = 'active'" in statement
    assert "b.is_active = TRUE" in statement


@pytest.mark.asyncio
async def test_ensure_unique_slug_for_create_omits_nullable_exclude_parameter() -> None:
    db = _SlugDb([None])
    service = ProductService(db=db)

    slug = await service._ensure_unique_slug("qa-slug")

    assert slug == "qa-slug"
    statement = _normalize_sql(db.statements[0])
    assert "WHERE slug = :slug LIMIT 1" in statement
    assert "exclude_product_id" not in statement
    assert db.params[0] == {"slug": "qa-slug"}


@pytest.mark.asyncio
async def test_ensure_unique_slug_for_update_excludes_current_product() -> None:
    db = _SlugDb([None])
    service = ProductService(db=db)
    product_id = uuid4()

    slug = await service._ensure_unique_slug("qa-slug", exclude_product_id=product_id)

    assert slug == "qa-slug"
    statement = _normalize_sql(db.statements[0])
    assert "AND id != :exclude_product_id" in statement
    assert db.params[0] == {"slug": "qa-slug", "exclude_product_id": product_id}


@pytest.mark.asyncio
async def test_brand_portal_list_keeps_brand_scope_without_public_visibility_gate() -> None:
    db = _CatalogDb()
    service = ProductService(db=db)

    items, total = await service.list_brand_products(
        brand_id=uuid4(),
        product_status=None,
        category=None,
        season=None,
        page=1,
        per_page=20,
    )

    assert items == []
    assert total == 0
    statement = _normalize_sql(db.statements[0])
    assert "p.brand_id = :brand_id" in statement
    assert "CAST(:product_status AS text) IS NULL" in statement
    assert "OR p.product_status::text = CAST(:product_status AS text)" in statement
    assert "p.is_active = TRUE" not in statement
    assert "b.is_active = TRUE" not in statement


@pytest.mark.asyncio
async def test_brand_portal_detail_keeps_brand_scope_without_public_visibility_gate() -> None:
    db = _CatalogDb()
    service = ProductService(db=db)

    with pytest.raises(ValueError):
        await service.get_product_by_id_for_brand(product_id=uuid4(), brand_id=uuid4())

    statement = _normalize_sql(db.statements[0])
    assert "p.id = :product_id AND p.brand_id = :brand_id" in statement
    assert "p.is_active = TRUE" not in statement
    assert "p.product_status = 'active'" not in statement
    assert "b.is_active = TRUE" not in statement


@pytest.mark.asyncio
async def test_add_image_commits_by_default_for_single_image_callers() -> None:
    db = _ImageDb()
    service = ProductService(db=db)

    image = await service.add_image(
        product_id=uuid4(),
        url="https://cdn.example/image.jpg",
        sort_order=0,
        alt_text=None,
    )

    assert image["id"] == db.image_id
    assert db.commits == 1


@pytest.mark.asyncio
async def test_add_image_can_defer_commit_for_batch_callers() -> None:
    db = _ImageDb()
    service = ProductService(db=db)

    image = await service.add_image(
        product_id=uuid4(),
        url="https://cdn.example/image.jpg",
        sort_order=0,
        alt_text=None,
        commit=False,
    )

    assert image["id"] == db.image_id
    assert db.commits == 0


@pytest.mark.asyncio
async def test_lock_product_for_image_upload_uses_row_lock() -> None:
    product_id = uuid4()
    db = _ProductLockDb(product_id=product_id)
    service = ProductService(db=db)

    await service.lock_product_for_image_upload(product_id=product_id)

    assert (
        _normalize_sql(db.statements[0])
        == "SELECT id FROM products WHERE id = :product_id FOR UPDATE"
    )
    assert db.params[0] == {"product_id": product_id}
