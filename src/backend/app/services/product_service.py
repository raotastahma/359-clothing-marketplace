from __future__ import annotations

import re

# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.product import (
    ProductCreateRequest,
    ProductImageReorderRequest,
    ProductStatusLiteral,
    ProductUpdateRequest,
    ProductVariantCreateRequest,
    ProductVariantUpdateRequest,
)

SortOption = Literal["price_asc", "price_desc", "newest"]
SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class CatalogFilters:
    brand: str | None
    category: str | None
    gender: str | None
    price_min: Decimal | None
    price_max: Decimal | None
    size: str | None
    is_sale: bool | None
    sort: SortOption
    page: int
    per_page: int


@beartype
def _to_slug(raw: str) -> str:
    slug = SLUG_RE.sub("-", raw.strip().lower()).strip("-")
    if slug:
        return slug
    return f"product-{uuid4().hex[:8]}"


@beartype
def _sizes_from_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, tuple):
        return [str(item) for item in value if item is not None]
    return [str(value)]


@beartype
def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError("Expected integer-compatible value.")


class ProductService:
    @beartype
    def __init__(self, *, db: AsyncSession) -> None:
        self._db = db

    @beartype
    async def create_product(self, *, payload: ProductCreateRequest) -> dict[str, object]:
        await self._assert_brand_exists(brand_id=payload.brand_id)
        await self._assert_category_exists(category_id=payload.category_id)
        unique_slug = await self._ensure_unique_slug(_to_slug(payload.slug or payload.name))

        created = await self._db.execute(
            sa.text(
                """
                INSERT INTO products (
                    brand_id,
                    category_id,
                    name,
                    slug,
                    description,
                    fabric_composition,
                    care_instructions,
                    season,
                    base_price_rub,
                    sale_price_rub,
                    product_status,
                    is_new_arrival,
                    is_active
                )
                VALUES (
                    :brand_id,
                    :category_id,
                    :name,
                    :slug,
                    :description,
                    :fabric_composition,
                    :care_instructions,
                    :season,
                    :base_price_rub,
                    :sale_price_rub,
                    :product_status,
                    :is_new_arrival,
                    :is_active
                )
                RETURNING id
                """
            ),
            {
                "brand_id": payload.brand_id,
                "category_id": payload.category_id,
                "name": payload.name,
                "slug": unique_slug,
                "description": payload.description,
                "fabric_composition": payload.fabric_composition,
                "care_instructions": payload.care_instructions,
                "season": payload.season,
                "base_price_rub": payload.base_price_rub,
                "sale_price_rub": payload.sale_price_rub,
                "product_status": payload.product_status,
                "is_new_arrival": payload.is_new_arrival,
                "is_active": payload.is_active,
            },
        )
        created_row = created.mappings().first()
        if created_row is None:
            raise RuntimeError("Failed to create product.")
        product_id = UUID(str(created_row["id"]))

        for variant in payload.variants:
            await self._insert_variant(product_id=product_id, payload=variant)

        await self._db.commit()
        return await self.get_product_by_id(product_id=product_id)

    @beartype
    async def update_product(
        self,
        *,
        product_id: UUID,
        payload: ProductUpdateRequest,
    ) -> dict[str, object]:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return await self.get_product_by_id(product_id=product_id)

        set_parts: list[str] = []
        params: dict[str, object] = {"product_id": product_id}

        if "name" in updates:
            set_parts.append("name = :name")
            params["name"] = updates["name"]
        if "slug" in updates:
            raw_slug = cast(str | None, updates["slug"])
            if raw_slug is None:
                raise ValueError("slug cannot be null.")
            unique_slug = await self._ensure_unique_slug(
                _to_slug(raw_slug),
                exclude_product_id=product_id,
            )
            set_parts.append("slug = :slug")
            params["slug"] = unique_slug
        if "description" in updates:
            set_parts.append("description = :description")
            params["description"] = updates["description"]
        if "fabric_composition" in updates:
            set_parts.append("fabric_composition = :fabric_composition")
            params["fabric_composition"] = updates["fabric_composition"]
        if "care_instructions" in updates:
            set_parts.append("care_instructions = :care_instructions")
            params["care_instructions"] = updates["care_instructions"]
        if "brand_id" in updates:
            brand_id = cast(UUID | None, updates["brand_id"])
            if brand_id is None:
                raise ValueError("brand_id cannot be null.")
            await self._assert_brand_exists(brand_id=brand_id)
            set_parts.append("brand_id = :brand_id")
            params["brand_id"] = brand_id
        if "category_id" in updates:
            category_id = cast(UUID | None, updates["category_id"])
            if category_id is None:
                raise ValueError("category_id cannot be null.")
            await self._assert_category_exists(category_id=category_id)
            set_parts.append("category_id = :category_id")
            params["category_id"] = category_id
        if "season" in updates:
            set_parts.append("season = :season")
            params["season"] = updates["season"]
        if "base_price_rub" in updates:
            set_parts.append("base_price_rub = :base_price_rub")
            params["base_price_rub"] = updates["base_price_rub"]
        if "sale_price_rub" in updates:
            set_parts.append("sale_price_rub = :sale_price_rub")
            params["sale_price_rub"] = updates["sale_price_rub"]
        if "product_status" in updates:
            set_parts.append("product_status = :product_status")
            params["product_status"] = updates["product_status"]
        if "is_new_arrival" in updates:
            set_parts.append("is_new_arrival = :is_new_arrival")
            params["is_new_arrival"] = updates["is_new_arrival"]
        if "is_active" in updates:
            set_parts.append("is_active = :is_active")
            params["is_active"] = updates["is_active"]

        if not set_parts:
            return await self.get_product_by_id(product_id=product_id)

        set_parts.append("updated_at = now()")
        query = f"UPDATE products SET {', '.join(set_parts)} WHERE id = :product_id RETURNING id"
        result = await self._db.execute(sa.text(query), params)
        if result.mappings().first() is None:
            raise ValueError("Product not found.")

        await self._db.commit()
        return await self.get_product_by_id(product_id=product_id)

    @beartype
    async def archive_product(self, *, product_id: UUID) -> dict[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                UPDATE products
                SET product_status = 'archived',
                    is_active = FALSE,
                    updated_at = now()
                WHERE id = :product_id
                RETURNING id
                """
            ),
            {"product_id": product_id},
        )
        if result.mappings().first() is None:
            raise ValueError("Product not found.")
        await self._db.commit()
        return await self.get_product_by_id(product_id=product_id)

    @beartype
    async def add_variant(
        self,
        *,
        product_id: UUID,
        payload: ProductVariantCreateRequest,
    ) -> dict[str, object]:
        await self._assert_product_exists(product_id=product_id)
        row = await self._insert_variant(product_id=product_id, payload=payload)
        await self._db.commit()
        return self._variant_from_row(row)

    @beartype
    async def update_variant(
        self,
        *,
        product_id: UUID,
        variant_id: UUID,
        payload: ProductVariantUpdateRequest,
    ) -> dict[str, object]:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return await self.get_variant(product_id=product_id, variant_id=variant_id)

        set_parts: list[str] = []
        params: dict[str, object] = {"product_id": product_id, "variant_id": variant_id}
        for field in (
            "vendor_code",
            "size",
            "color",
            "sku",
            "price_rub",
            "compare_at_price_rub",
            "stock_quantity",
            "is_active",
        ):
            if field in updates:
                set_parts.append(f"{field} = :{field}")
                params[field] = updates[field]

        if not set_parts:
            return await self.get_variant(product_id=product_id, variant_id=variant_id)

        result = await self._db.execute(
            sa.text(
                f"""
                UPDATE product_variants
                SET {", ".join(set_parts)}
                WHERE id = :variant_id
                  AND product_id = :product_id
                RETURNING id
                """
            ),
            params,
        )
        if result.mappings().first() is None:
            raise ValueError("Variant not found.")

        await self._db.commit()
        return await self.get_variant(product_id=product_id, variant_id=variant_id)

    @beartype
    async def delete_variant(self, *, product_id: UUID, variant_id: UUID) -> None:
        result = await self._db.execute(
            sa.text(
                """
                DELETE FROM product_variants
                WHERE id = :variant_id
                  AND product_id = :product_id
                RETURNING id
                """
            ),
            {"variant_id": variant_id, "product_id": product_id},
        )
        if result.mappings().first() is None:
            raise ValueError("Variant not found.")
        await self._db.commit()

    @beartype
    async def add_image(
        self,
        *,
        product_id: UUID,
        url: str,
        sort_order: int,
        alt_text: str | None,
        commit: bool = True,
    ) -> dict[str, object]:
        await self._assert_product_exists(product_id=product_id)
        result = await self._db.execute(
            sa.text(
                """
                INSERT INTO product_images (product_id, url, sort_order, alt_text)
                VALUES (:product_id, :url, :sort_order, :alt_text)
                RETURNING id, url, sort_order, alt_text
                """
            ),
            {
                "product_id": product_id,
                "url": url,
                "sort_order": sort_order,
                "alt_text": alt_text,
            },
        )
        row = result.mappings().first()
        if row is None:
            raise RuntimeError("Failed to add image.")
        if commit:
            await self._db.commit()
        return self._image_from_row(cast(Mapping[str, object], row))

    @beartype
    async def get_image(self, *, product_id: UUID, image_id: UUID) -> dict[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT id, url, sort_order, alt_text
                FROM product_images
                WHERE id = :image_id
                  AND product_id = :product_id
                LIMIT 1
                """
            ),
            {"image_id": image_id, "product_id": product_id},
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("Image not found.")
        return self._image_from_row(cast(Mapping[str, object], row))

    @beartype
    async def delete_image(self, *, product_id: UUID, image_id: UUID) -> str:
        existing = await self.get_image(product_id=product_id, image_id=image_id)
        await self._db.execute(
            sa.text(
                """
                DELETE FROM product_images
                WHERE id = :image_id
                  AND product_id = :product_id
                """
            ),
            {"image_id": image_id, "product_id": product_id},
        )
        await self._db.commit()
        return str(existing["url"])

    @beartype
    async def reorder_images(
        self,
        *,
        product_id: UUID,
        payload: ProductImageReorderRequest,
    ) -> list[dict[str, object]]:
        for item in payload.items:
            result = await self._db.execute(
                sa.text(
                    """
                    UPDATE product_images
                    SET sort_order = :sort_order
                    WHERE id = :image_id
                      AND product_id = :product_id
                    RETURNING id
                    """
                ),
                {
                    "sort_order": item.sort_order,
                    "image_id": item.image_id,
                    "product_id": product_id,
                },
            )
            if result.mappings().first() is None:
                raise ValueError("Image not found.")
        await self._db.commit()
        return await self.list_images(product_id=product_id)

    @beartype
    async def list_images(self, *, product_id: UUID) -> list[dict[str, object]]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT id, url, sort_order, alt_text
                FROM product_images
                WHERE product_id = :product_id
                ORDER BY sort_order ASC, id ASC
                """
            ),
            {"product_id": product_id},
        )
        rows = result.mappings().all()
        return [self._image_from_row(cast(Mapping[str, object], row)) for row in rows]

    @beartype
    async def lock_product_for_image_upload(self, *, product_id: UUID) -> None:
        result = await self._db.execute(
            sa.text(
                """
                SELECT id
                FROM products
                WHERE id = :product_id
                FOR UPDATE
                """
            ),
            {"product_id": product_id},
        )
        if result.mappings().first() is None:
            raise ValueError("Product not found.")

    @beartype
    async def get_product_by_slug(self, *, slug: str) -> dict[str, object]:
        row = await self._get_product_row(
            where_sql=(
                "p.slug = :slug AND p.is_active = TRUE "
                "AND p.product_status = 'active' AND b.is_active = TRUE"
            ),
            params={"slug": slug},
        )
        product_id = UUID(str(row["id"]))
        return await self._build_product_detail(row=row, product_id=product_id)

    @beartype
    async def get_product_by_id(self, *, product_id: UUID) -> dict[str, object]:
        row = await self._get_product_row(
            where_sql="p.id = :product_id",
            params={"product_id": product_id},
        )
        return await self._build_product_detail(row=row, product_id=product_id)

    @beartype
    async def get_product_by_id_for_brand(
        self,
        *,
        product_id: UUID,
        brand_id: UUID,
    ) -> dict[str, object]:
        row = await self._get_product_row(
            where_sql="p.id = :product_id AND p.brand_id = :brand_id",
            params={"product_id": product_id, "brand_id": brand_id},
        )
        return await self._build_product_detail(row=row, product_id=product_id)

    @beartype
    async def list_brand_products(
        self,
        *,
        brand_id: UUID,
        product_status: ProductStatusLiteral | None,
        category: str | None,
        season: str | None,
        page: int,
        per_page: int,
    ) -> tuple[list[dict[str, object]], int]:
        offset = (page - 1) * per_page
        params: dict[str, object] = {
            "brand_id": brand_id,
            "product_status": product_status,
            "category_slug": category,
            "season": season,
            "limit": per_page,
            "offset": offset,
        }
        where_clause = (
            "p.brand_id = :brand_id "
            "AND ("
            "    CAST(:product_status AS text) IS NULL "
            "    OR p.product_status::text = CAST(:product_status AS text)"
            ") "
            "AND ("
            "    CAST(:category_slug AS text) IS NULL "
            "    OR c.slug = CAST(:category_slug AS text)"
            ") "
            "AND (CAST(:season AS text) IS NULL OR p.season = CAST(:season AS text))"
        )
        result = await self._db.execute(
            sa.text(
                f"""
                SELECT
                    p.id,
                    p.name,
                    p.slug,
                    p.description,
                    p.fabric_composition,
                    p.care_instructions,
                    p.season,
                    p.base_price_rub,
                    p.sale_price_rub,
                    p.product_status,
                    p.is_active,
                    p.is_new_arrival,
                    p.created_at,
                    b.id AS brand_id,
                    b.name AS brand_name,
                    b.slug AS brand_slug,
                    b.logo_url AS brand_logo_url,
                    c.id AS category_id,
                    c.name AS category_name,
                    c.slug AS category_slug,
                    c.gender AS category_gender,
                    cp.name AS parent_name,
                    cp.slug AS parent_slug
                FROM products p
                JOIN brands b ON b.id = p.brand_id
                JOIN categories c ON c.id = p.category_id
                LEFT JOIN categories cp ON cp.id = c.parent_id
                WHERE {where_clause}
                ORDER BY p.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        rows = result.mappings().all()

        total_result = await self._db.execute(
            sa.text(
                f"""
                SELECT COUNT(*) AS total
                FROM products p
                JOIN categories c ON c.id = p.category_id
                WHERE {where_clause}
                """
            ),
            params,
        )
        total_row = total_result.mappings().first()
        total = int(total_row["total"]) if total_row is not None else 0

        items = [
            await self._build_product_detail(
                row=cast(Mapping[str, object], row),
                product_id=UUID(str(row["id"])),
            )
            for row in rows
        ]
        return items, total

    @beartype
    async def list_variants(self, *, product_id: UUID) -> list[dict[str, object]]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    id,
                    vendor_code,
                    size,
                    color,
                    sku,
                    price_rub,
                    compare_at_price_rub,
                    stock_quantity,
                    is_active
                FROM product_variants
                WHERE product_id = :product_id
                ORDER BY size ASC, sku ASC
                """
            ),
            {"product_id": product_id},
        )
        return [
            self._variant_from_row(cast(Mapping[str, object], row))
            for row in result.mappings().all()
        ]

    @beartype
    async def count_images(self, *, product_id: UUID) -> int:
        result = await self._db.execute(
            sa.text(
                """
                SELECT COUNT(*) AS image_count
                FROM product_images
                WHERE product_id = :product_id
                """
            ),
            {"product_id": product_id},
        )
        row = result.mappings().first()
        if row is None:
            return 0
        return _to_int(row["image_count"])

    @beartype
    async def list_products(
        self,
        *,
        filters: CatalogFilters,
    ) -> tuple[list[dict[str, object]], int]:
        offset = (filters.page - 1) * filters.per_page
        order_by = self._resolve_sort(filters.sort)
        params: dict[str, object] = {
            "brand_slug": filters.brand,
            "category_slug": filters.category,
            "gender": filters.gender,
            "price_min": filters.price_min,
            "price_max": filters.price_max,
            "size_filter": filters.size,
            "is_sale": filters.is_sale,
            "limit": filters.per_page,
            "offset": offset,
        }

        where_clause = self._catalog_where_clause()
        result = await self._db.execute(
            sa.text(
                f"""
                SELECT
                    p.id,
                    p.name,
                    p.slug,
                    p.is_new_arrival,
                    b.id AS brand_id,
                    b.name AS brand_name,
                    b.slug AS brand_slug,
                    b.logo_url AS brand_logo_url,
                    c.id AS category_id,
                    c.name AS category_name,
                    c.slug AS category_slug,
                    c.gender AS category_gender,
                    (
                        SELECT MIN(v.price_rub)
                        FROM product_variants v
                        WHERE v.product_id = p.id
                          AND v.is_active = TRUE
                    ) AS price_from,
                    (
                        SELECT MIN(v.compare_at_price_rub)
                        FROM product_variants v
                        WHERE v.product_id = p.id
                          AND v.is_active = TRUE
                          AND v.compare_at_price_rub IS NOT NULL
                    ) AS compare_at_price_from,
                    COALESCE(
                        (
                            SELECT array_agg(DISTINCT sv.size)
                            FROM product_variants sv
                            WHERE sv.product_id = p.id
                              AND sv.is_active = TRUE
                              AND sv.stock_quantity > 0
                        ),
                        ARRAY[]::varchar[]
                    ) AS available_sizes,
                    (
                        SELECT jsonb_build_object(
                            'id',
                            pi.id,
                            'url',
                            pi.url,
                            'sort_order',
                            pi.sort_order,
                            'alt_text',
                            pi.alt_text
                        )
                        FROM product_images pi
                        WHERE pi.product_id = p.id
                        ORDER BY pi.sort_order ASC, pi.id ASC
                        LIMIT 1
                    ) AS primary_image
                FROM products p
                JOIN brands b ON b.id = p.brand_id
                JOIN categories c ON c.id = p.category_id
                WHERE {where_clause}
                ORDER BY {order_by}
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        rows = result.mappings().all()

        total_result = await self._db.execute(
            sa.text(
                f"""
                SELECT COUNT(*) AS total
                FROM products p
                JOIN brands b ON b.id = p.brand_id
                JOIN categories c ON c.id = p.category_id
                WHERE {where_clause}
                """
            ),
            params,
        )
        total_row = total_result.mappings().first()
        total = int(total_row["total"]) if total_row is not None else 0

        return [self._catalog_item_from_row(cast(Mapping[str, object], row)) for row in rows], total

    @beartype
    async def search_products(
        self,
        *,
        query: str,
        page: int,
        per_page: int,
    ) -> tuple[list[dict[str, object]], int]:
        offset = (page - 1) * per_page
        params = {"q": query, "limit": per_page, "offset": offset}
        where_clause = (
            "p.is_active = TRUE "
            "AND p.product_status = 'active' "
            "AND b.is_active = TRUE "
            "AND ("
            "to_tsvector('russian', p.name || ' ' || COALESCE(p.description, '')) "
            "@@ plainto_tsquery('russian', :q) "
            "OR p.name ILIKE '%' || :q || '%' "
            "OR COALESCE(p.description, '') ILIKE '%' || :q || '%'"
            ")"
        )

        result = await self._db.execute(
            sa.text(
                f"""
                SELECT
                    p.id,
                    p.name,
                    p.slug,
                    p.is_new_arrival,
                    b.id AS brand_id,
                    b.name AS brand_name,
                    b.slug AS brand_slug,
                    b.logo_url AS brand_logo_url,
                    c.id AS category_id,
                    c.name AS category_name,
                    c.slug AS category_slug,
                    c.gender AS category_gender,
                    (
                        SELECT MIN(v.price_rub)
                        FROM product_variants v
                        WHERE v.product_id = p.id
                          AND v.is_active = TRUE
                    ) AS price_from,
                    (
                        SELECT MIN(v.compare_at_price_rub)
                        FROM product_variants v
                        WHERE v.product_id = p.id
                          AND v.is_active = TRUE
                          AND v.compare_at_price_rub IS NOT NULL
                    ) AS compare_at_price_from,
                    COALESCE(
                        (
                            SELECT array_agg(DISTINCT sv.size)
                            FROM product_variants sv
                            WHERE sv.product_id = p.id
                              AND sv.is_active = TRUE
                              AND sv.stock_quantity > 0
                        ),
                        ARRAY[]::varchar[]
                    ) AS available_sizes,
                    (
                        SELECT jsonb_build_object(
                            'id',
                            pi.id,
                            'url',
                            pi.url,
                            'sort_order',
                            pi.sort_order,
                            'alt_text',
                            pi.alt_text
                        )
                        FROM product_images pi
                        WHERE pi.product_id = p.id
                        ORDER BY pi.sort_order ASC, pi.id ASC
                        LIMIT 1
                    ) AS primary_image
                FROM products p
                JOIN brands b ON b.id = p.brand_id
                JOIN categories c ON c.id = p.category_id
                WHERE {where_clause}
                ORDER BY p.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        rows = result.mappings().all()

        total_result = await self._db.execute(
            sa.text(
                f"""
                SELECT COUNT(*) AS total
                FROM products p
                JOIN brands b ON b.id = p.brand_id
                JOIN categories c ON c.id = p.category_id
                WHERE {where_clause}
                """
            ),
            params,
        )
        total_row = total_result.mappings().first()
        total = int(total_row["total"]) if total_row is not None else 0

        return [self._catalog_item_from_row(cast(Mapping[str, object], row)) for row in rows], total

    @beartype
    async def list_public_brands(
        self,
        *,
        page: int,
        per_page: int,
    ) -> tuple[list[dict[str, object]], int]:
        offset = (page - 1) * per_page
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    b.id,
                    b.name,
                    b.slug,
                    b.description,
                    b.logo_url,
                    b.cover_url,
                    (
                        SELECT COUNT(*)
                        FROM products p
                        WHERE p.brand_id = b.id
                          AND p.is_active = TRUE
                          AND p.product_status = 'active'
                    ) AS products_count
                FROM brands b
                WHERE b.is_active = TRUE
                ORDER BY b.name ASC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": per_page, "offset": offset},
        )
        rows = result.mappings().all()

        count_result = await self._db.execute(
            sa.text("SELECT COUNT(*) AS total FROM brands WHERE is_active = TRUE")
        )
        count_row = count_result.mappings().first()
        total = int(count_row["total"]) if count_row is not None else 0

        return [self._brand_from_row(cast(Mapping[str, object], row)) for row in rows], total

    @beartype
    async def get_public_brand_by_slug(self, *, slug: str) -> dict[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    b.id,
                    b.name,
                    b.slug,
                    b.description,
                    b.logo_url,
                    b.cover_url,
                    (
                        SELECT COUNT(*)
                        FROM products p
                        WHERE p.brand_id = b.id
                          AND p.is_active = TRUE
                          AND p.product_status = 'active'
                    ) AS products_count
                FROM brands b
                WHERE b.slug = :slug
                  AND b.is_active = TRUE
                LIMIT 1
                """
            ),
            {"slug": slug},
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("Brand not found.")
        return self._brand_from_row(cast(Mapping[str, object], row))

    @beartype
    async def get_categories_tree(self) -> list[dict[str, object]]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT id, parent_id, name, slug, gender, sort_order
                FROM categories
                ORDER BY sort_order ASC, name ASC
                """
            )
        )
        rows = result.mappings().all()
        nodes: dict[UUID, dict[str, object]] = {}
        children: dict[UUID, list[dict[str, object]]] = defaultdict(list)
        roots: list[dict[str, object]] = []

        for row in rows:
            node_id = UUID(str(row["id"]))
            nodes[node_id] = {
                "id": node_id,
                "name": str(row["name"]),
                "slug": str(row["slug"]),
                "gender": str(row["gender"]),
                "children": [],
            }

        for row in rows:
            node_id = UUID(str(row["id"]))
            parent_value = row["parent_id"]
            if parent_value is None:
                roots.append(nodes[node_id])
                continue
            parent_id = UUID(str(parent_value))
            children[parent_id].append(nodes[node_id])

        for parent_id, items in children.items():
            parent = nodes.get(parent_id)
            if parent is not None:
                parent["children"] = items

        return roots

    @beartype
    async def _insert_variant(
        self,
        *,
        product_id: UUID,
        payload: ProductVariantCreateRequest,
    ) -> Mapping[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                INSERT INTO product_variants (
                    product_id,
                    vendor_code,
                    size,
                    color,
                    sku,
                    price_rub,
                    compare_at_price_rub,
                    stock_quantity,
                    is_active
                )
                VALUES (
                    :product_id,
                    :vendor_code,
                    :size,
                    :color,
                    :sku,
                    :price_rub,
                    :compare_at_price_rub,
                    :stock_quantity,
                    :is_active
                )
                RETURNING
                    id,
                    vendor_code,
                    size,
                    color,
                    sku,
                    price_rub,
                    compare_at_price_rub,
                    stock_quantity,
                    is_active
                """
            ),
            {
                "product_id": product_id,
                "vendor_code": payload.vendor_code,
                "size": payload.size,
                "color": payload.color,
                "sku": payload.sku,
                "price_rub": payload.price_rub,
                "compare_at_price_rub": payload.compare_at_price_rub,
                "stock_quantity": payload.stock_quantity,
                "is_active": payload.is_active,
            },
        )
        row = result.mappings().first()
        if row is None:
            raise RuntimeError("Failed to create variant.")
        return cast(Mapping[str, object], row)

    @beartype
    async def get_variant(self, *, product_id: UUID, variant_id: UUID) -> dict[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    id,
                    vendor_code,
                    size,
                    color,
                    sku,
                    price_rub,
                    compare_at_price_rub,
                    stock_quantity,
                    is_active
                FROM product_variants
                WHERE id = :variant_id
                  AND product_id = :product_id
                LIMIT 1
                """
            ),
            {"variant_id": variant_id, "product_id": product_id},
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("Variant not found.")
        return self._variant_from_row(cast(Mapping[str, object], row))

    @beartype
    async def _build_product_detail(
        self,
        *,
        row: Mapping[str, object],
        product_id: UUID,
    ) -> dict[str, object]:
        variants_result = await self._db.execute(
            sa.text(
                """
                SELECT
                    id,
                    vendor_code,
                    size,
                    color,
                    sku,
                    price_rub,
                    compare_at_price_rub,
                    stock_quantity,
                    is_active
                FROM product_variants
                WHERE product_id = :product_id
                ORDER BY size ASC, sku ASC
                """
            ),
            {"product_id": product_id},
        )
        variants = [
            self._variant_from_row(cast(Mapping[str, object], item))
            for item in variants_result.mappings().all()
        ]

        images = await self.list_images(product_id=product_id)
        return {
            "id": product_id,
            "name": str(row["name"]),
            "slug": str(row["slug"]),
            "description": cast(str | None, row["description"]),
            "fabric_composition": cast(str | None, row["fabric_composition"]),
            "care_instructions": cast(str | None, row["care_instructions"]),
            "season": cast(str | None, row["season"]),
            "base_price_rub": row["base_price_rub"],
            "sale_price_rub": row["sale_price_rub"],
            "product_status": str(row["product_status"]),
            "is_active": bool(row["is_active"]),
            "is_new_arrival": bool(row["is_new_arrival"]),
            "created_at": row["created_at"],
            "brand": {
                "id": UUID(str(row["brand_id"])),
                "name": str(row["brand_name"]),
                "slug": str(row["brand_slug"]),
                "logo_url": cast(str | None, row["brand_logo_url"]),
            },
            "category": {
                "id": UUID(str(row["category_id"])),
                "name": str(row["category_name"]),
                "slug": str(row["category_slug"]),
                "gender": str(row["category_gender"]),
                "parent": (
                    {
                        "name": str(row["parent_name"]),
                        "slug": str(row["parent_slug"]),
                    }
                    if row["parent_name"] is not None and row["parent_slug"] is not None
                    else None
                ),
            },
            "variants": variants,
            "images": images,
        }

    @beartype
    async def _get_product_row(
        self,
        *,
        where_sql: str,
        params: Mapping[str, object],
    ) -> Mapping[str, object]:
        result = await self._db.execute(
            sa.text(
                f"""
                SELECT
                    p.id,
                    p.name,
                    p.slug,
                    p.description,
                    p.fabric_composition,
                    p.care_instructions,
                    p.season,
                    p.base_price_rub,
                    p.sale_price_rub,
                    p.product_status,
                    p.is_active,
                    p.is_new_arrival,
                    p.created_at,
                    b.id AS brand_id,
                    b.name AS brand_name,
                    b.slug AS brand_slug,
                    b.logo_url AS brand_logo_url,
                    c.id AS category_id,
                    c.name AS category_name,
                    c.slug AS category_slug,
                    c.gender AS category_gender,
                    cp.name AS parent_name,
                    cp.slug AS parent_slug
                FROM products p
                JOIN brands b ON b.id = p.brand_id
                JOIN categories c ON c.id = p.category_id
                LEFT JOIN categories cp ON cp.id = c.parent_id
                WHERE {where_sql}
                LIMIT 1
                """
            ),
            dict(params),
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("Product not found.")
        return cast(Mapping[str, object], row)

    @beartype
    async def _assert_brand_exists(self, *, brand_id: UUID) -> None:
        result = await self._db.execute(
            sa.text("SELECT 1 FROM brands WHERE id = :brand_id LIMIT 1"),
            {"brand_id": brand_id},
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("Brand not found.")

    @beartype
    async def _assert_category_exists(self, *, category_id: UUID) -> None:
        result = await self._db.execute(
            sa.text("SELECT 1 FROM categories WHERE id = :category_id LIMIT 1"),
            {"category_id": category_id},
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("Category not found.")

    @beartype
    async def _assert_product_exists(self, *, product_id: UUID) -> None:
        result = await self._db.execute(
            sa.text("SELECT 1 FROM products WHERE id = :product_id LIMIT 1"),
            {"product_id": product_id},
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("Product not found.")

    @beartype
    async def _ensure_unique_slug(
        self,
        base_slug: str,
        *,
        exclude_product_id: UUID | None = None,
    ) -> str:
        candidate = base_slug
        suffix = 2
        while True:
            params: dict[str, object] = {"slug": candidate}
            exclude_predicate = ""
            if exclude_product_id is not None:
                exclude_predicate = "AND id != :exclude_product_id"
                params["exclude_product_id"] = exclude_product_id

            result = await self._db.execute(
                sa.text(
                    f"""
                    SELECT 1
                    FROM products
                    WHERE slug = :slug
                      {exclude_predicate}
                    LIMIT 1
                    """
                ),
                params,
            )
            if result.scalar_one_or_none() is None:
                return candidate
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

    @beartype
    def _resolve_sort(self, sort: SortOption) -> str:
        mapping: dict[str, str] = {
            "price_asc": "price_from ASC NULLS LAST, p.created_at DESC",
            "price_desc": "price_from DESC NULLS LAST, p.created_at DESC",
            "newest": "p.created_at DESC",
        }
        return mapping[sort]

    @beartype
    def _catalog_where_clause(self) -> str:
        return (
            "p.is_active = TRUE "
            "AND p.product_status = 'active' "
            "AND b.is_active = TRUE "
            "AND (CAST(:brand_slug AS text) IS NULL OR b.slug = CAST(:brand_slug AS text)) "
            "AND ("
            "    CAST(:category_slug AS text) IS NULL "
            "    OR p.category_id IN ("
            "        WITH RECURSIVE category_scope AS ("
            "            SELECT id "
            "            FROM categories "
            "            WHERE slug = CAST(:category_slug AS text) "
            "            UNION ALL "
            "            SELECT child.id "
            "            FROM categories child "
            "            JOIN category_scope parent ON child.parent_id = parent.id"
            "        ) "
            "        SELECT id FROM category_scope"
            "    )"
            ") "
            "AND (CAST(:gender AS text) IS NULL OR c.gender::text = CAST(:gender AS text)) "
            "AND ("
            "    CAST(:price_min AS numeric) IS NULL "
            "    OR EXISTS ("
            "        SELECT 1 FROM product_variants pv_min "
            "        WHERE pv_min.product_id = p.id "
            "          AND pv_min.is_active = TRUE "
            "          AND pv_min.price_rub >= CAST(:price_min AS numeric)"
            "    )"
            ") "
            "AND ("
            "    CAST(:price_max AS numeric) IS NULL "
            "    OR EXISTS ("
            "        SELECT 1 FROM product_variants pv_max "
            "        WHERE pv_max.product_id = p.id "
            "          AND pv_max.is_active = TRUE "
            "          AND pv_max.price_rub <= CAST(:price_max AS numeric)"
            "    )"
            ") "
            "AND ("
            "    CAST(:is_sale AS boolean) IS NOT TRUE "
            "    OR EXISTS ("
            "        SELECT 1 FROM product_variants sale_v "
            "        WHERE sale_v.product_id = p.id "
            "          AND sale_v.is_active = TRUE "
            "          AND sale_v.compare_at_price_rub IS NOT NULL "
            "          AND sale_v.compare_at_price_rub > sale_v.price_rub"
            "    )"
            ") "
            "AND ("
            "    CAST(:size_filter AS text) IS NULL "
            "    OR EXISTS ("
            "        SELECT 1 FROM product_variants sv "
            "        WHERE sv.product_id = p.id "
            "          AND sv.size = ANY(string_to_array(CAST(:size_filter AS text), ',')) "
            "          AND sv.is_active = TRUE "
            "          AND sv.stock_quantity > 0"
            "    )"
            ")"
        )

    @beartype
    def _variant_from_row(self, row: Mapping[str, object]) -> dict[str, object]:
        return {
            "id": UUID(str(row["id"])),
            "vendor_code": cast(str | None, row["vendor_code"]),
            "size": str(row["size"]),
            "color": cast(str | None, row["color"]),
            "sku": str(row["sku"]),
            "price_rub": row["price_rub"],
            "compare_at_price_rub": row["compare_at_price_rub"],
            "stock_quantity": _to_int(row["stock_quantity"]),
            "is_active": bool(row["is_active"]),
        }

    @beartype
    def _image_from_row(self, row: Mapping[str, object]) -> dict[str, object]:
        return {
            "id": UUID(str(row["id"])),
            "url": str(row["url"]),
            "sort_order": _to_int(row["sort_order"]),
            "alt_text": cast(str | None, row["alt_text"]),
        }

    @beartype
    def _catalog_item_from_row(self, row: Mapping[str, object]) -> dict[str, object]:
        image_payload: list[dict[str, object]] = []
        primary_image = row["primary_image"]
        if isinstance(primary_image, dict):
            image_payload.append(
                {
                    "id": UUID(str(primary_image.get("id"))),
                    "url": str(primary_image.get("url", "")),
                    "sort_order": int(primary_image.get("sort_order", 0)),
                    "alt_text": (
                        str(primary_image["alt_text"])
                        if primary_image.get("alt_text") is not None
                        else None
                    ),
                }
            )
        return {
            "id": UUID(str(row["id"])),
            "name": str(row["name"]),
            "slug": str(row["slug"]),
            "brand": {
                "id": UUID(str(row["brand_id"])),
                "name": str(row["brand_name"]),
                "slug": str(row["brand_slug"]),
                "logo_url": cast(str | None, row["brand_logo_url"]),
            },
            "category": {
                "id": UUID(str(row["category_id"])),
                "name": str(row["category_name"]),
                "slug": str(row["category_slug"]),
                "gender": str(row["category_gender"]),
                "parent": None,
            },
            "price_from": row["price_from"],
            "compare_at_price_from": row["compare_at_price_from"],
            "is_new_arrival": bool(row["is_new_arrival"]),
            "images": image_payload,
            "available_sizes": _sizes_from_value(row["available_sizes"]),
        }

    @beartype
    def _brand_from_row(self, row: Mapping[str, object]) -> dict[str, object]:
        return {
            "id": UUID(str(row["id"])),
            "name": str(row["name"]),
            "slug": str(row["slug"]),
            "description": cast(str | None, row["description"]),
            "logo_url": cast(str | None, row["logo_url"]),
            "cover_url": cast(str | None, row["cover_url"]),
            "products_count": _to_int(row["products_count"]),
        }
