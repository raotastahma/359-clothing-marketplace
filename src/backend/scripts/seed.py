from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit
from uuid import UUID

import bcrypt
import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.database import async_session_factory


@dataclass(frozen=True)
class CategoryNode:
    name: str
    slug: str
    gender: str
    sort_order: int
    children: tuple[CategoryNode, ...] = ()


CATEGORY_TREE: Final[tuple[CategoryNode, ...]] = (
    CategoryNode(
        name="Men",
        slug="men",
        gender="men",
        sort_order=10,
        children=(
            CategoryNode(
                name="Clothing",
                slug="men-clothing",
                gender="men",
                sort_order=11,
                children=(
                    CategoryNode(name="Coats", slug="men-coats", gender="men", sort_order=1),
                    CategoryNode(name="Hoodies", slug="men-hoodies", gender="men", sort_order=2),
                    CategoryNode(name="Pants", slug="men-pants", gender="men", sort_order=3),
                    CategoryNode(name="T-Shirts", slug="men-t-shirts", gender="men", sort_order=4),
                    CategoryNode(name="Jeans", slug="men-jeans", gender="men", sort_order=5),
                    CategoryNode(name="Jackets", slug="men-jackets", gender="men", sort_order=6),
                    CategoryNode(name="Knitwear", slug="men-knitwear", gender="men", sort_order=7),
                    CategoryNode(
                        name="Underwear", slug="men-underwear", gender="men", sort_order=8
                    ),
                ),
            ),
            CategoryNode(
                name="Footwear",
                slug="men-footwear",
                gender="men",
                sort_order=12,
                children=(
                    CategoryNode(name="Sneakers", slug="men-sneakers", gender="men", sort_order=1),
                    CategoryNode(name="Boots", slug="men-boots", gender="men", sort_order=2),
                ),
            ),
            CategoryNode(
                name="Accessories",
                slug="men-accessories",
                gender="men",
                sort_order=13,
                children=(
                    CategoryNode(name="Bags", slug="men-bags", gender="men", sort_order=1),
                    CategoryNode(name="Hats", slug="men-hats", gender="men", sort_order=2),
                ),
            ),
            CategoryNode(
                name="Lifestyle",
                slug="men-lifestyle",
                gender="men",
                sort_order=14,
                children=(
                    CategoryNode(name="Home", slug="men-home", gender="men", sort_order=1),
                    CategoryNode(name="Care", slug="men-care", gender="men", sort_order=2),
                ),
            ),
        ),
    ),
    CategoryNode(
        name="Women",
        slug="women",
        gender="women",
        sort_order=20,
        children=(
            CategoryNode(
                name="Clothing",
                slug="women-clothing",
                gender="women",
                sort_order=21,
                children=(
                    CategoryNode(name="Coats", slug="women-coats", gender="women", sort_order=1),
                    CategoryNode(
                        name="Hoodies", slug="women-hoodies", gender="women", sort_order=2
                    ),
                    CategoryNode(name="Pants", slug="women-pants", gender="women", sort_order=3),
                    CategoryNode(
                        name="T-Shirts", slug="women-t-shirts", gender="women", sort_order=4
                    ),
                    CategoryNode(name="Jeans", slug="women-jeans", gender="women", sort_order=5),
                    CategoryNode(
                        name="Jackets", slug="women-jackets", gender="women", sort_order=6
                    ),
                    CategoryNode(
                        name="Knitwear", slug="women-knitwear", gender="women", sort_order=7
                    ),
                    CategoryNode(
                        name="Underwear", slug="women-underwear", gender="women", sort_order=8
                    ),
                ),
            ),
            CategoryNode(
                name="Footwear",
                slug="women-footwear",
                gender="women",
                sort_order=22,
                children=(
                    CategoryNode(
                        name="Sneakers", slug="women-sneakers", gender="women", sort_order=1
                    ),
                    CategoryNode(name="Boots", slug="women-boots", gender="women", sort_order=2),
                ),
            ),
            CategoryNode(
                name="Accessories",
                slug="women-accessories",
                gender="women",
                sort_order=23,
                children=(
                    CategoryNode(name="Bags", slug="women-bags", gender="women", sort_order=1),
                    CategoryNode(name="Hats", slug="women-hats", gender="women", sort_order=2),
                ),
            ),
            CategoryNode(
                name="Lifestyle",
                slug="women-lifestyle",
                gender="women",
                sort_order=24,
                children=(
                    CategoryNode(name="Home", slug="women-home", gender="women", sort_order=1),
                    CategoryNode(name="Care", slug="women-care", gender="women", sort_order=2),
                ),
            ),
        ),
    ),
)


@beartype
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@beartype
async def _upsert_category(
    session: AsyncSession,
    *,
    node: CategoryNode,
    parent_id: UUID | None,
) -> UUID:
    result = await session.execute(
        sa.text(
            """
            INSERT INTO categories (parent_id, name, slug, gender, sort_order)
            VALUES (:parent_id, :name, :slug, :gender, :sort_order)
            ON CONFLICT (slug) DO UPDATE
            SET
                parent_id = EXCLUDED.parent_id,
                name = EXCLUDED.name,
                gender = EXCLUDED.gender,
                sort_order = EXCLUDED.sort_order
            RETURNING id
            """
        ),
        {
            "parent_id": parent_id,
            "name": node.name,
            "slug": node.slug,
            "gender": node.gender,
            "sort_order": node.sort_order,
        },
    )
    category_id = result.scalar_one()
    if not isinstance(category_id, UUID):
        raise RuntimeError("Database returned non-UUID category id.")
    return category_id


@beartype
async def _seed_category_tree(
    session: AsyncSession,
    *,
    node: CategoryNode,
    parent_id: UUID | None,
) -> None:
    category_id = await _upsert_category(session, node=node, parent_id=parent_id)
    for child in node.children:
        await _seed_category_tree(session, node=child, parent_id=category_id)


@beartype
async def _seed_platform_settings(session: AsyncSession) -> None:
    settings_to_seed: tuple[tuple[str, str, str], ...] = (
        (
            "PAYOUT_DELAY_DAYS",
            "14",
            "Количество дней после доставки до выплаты бренду",
        ),
        (
            "DEFAULT_COMMISSION_RATE",
            "0.35",
            "Комиссия платформы по умолчанию (35%)",
        ),
    )
    for key, value, description in settings_to_seed:
        await session.execute(
            sa.text(
                """
                INSERT INTO platform_settings (key, value, description)
                VALUES (:key, :value, :description)
                ON CONFLICT (key) DO UPDATE
                SET
                    value = EXCLUDED.value,
                    description = EXCLUDED.description,
                    updated_at = now()
                """
            ),
            {
                "key": key,
                "value": value,
                "description": description,
            },
        )


@beartype
async def _seed_test_brand(session: AsyncSession) -> None:
    await session.execute(
        sa.text(
            """
            INSERT INTO brands (
                name,
                slug,
                description,
                commission_rate,
                founded_year,
                is_active
            )
            VALUES (
                :name,
                :slug,
                :description,
                :commission_rate,
                :founded_year,
                :is_active
            )
            ON CONFLICT (slug) DO UPDATE
            SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                commission_rate = EXCLUDED.commission_rate,
                founded_year = EXCLUDED.founded_year,
                is_active = EXCLUDED.is_active
            """
        ),
        {
            "name": "Test Brand",
            "slug": "test-brand",
            "description": "Development brand for local testing",
            "commission_rate": Decimal("0.35"),
            "founded_year": 2024,
            "is_active": True,
        },
    )


@beartype
async def _seed_admin_user(session: AsyncSession) -> None:
    await session.execute(
        sa.text(
            """
            INSERT INTO users (
                phone,
                email,
                name,
                is_verified,
                is_admin
            )
            VALUES (
                :phone,
                :email,
                :name,
                TRUE,
                TRUE
            )
            ON CONFLICT (phone) DO UPDATE
            SET
                email = EXCLUDED.email,
                name = EXCLUDED.name,
                is_verified = TRUE,
                is_admin = TRUE,
                updated_at = now()
            """
        ),
        {
            "phone": "+12025550101",
            "email": "admin@example.invalid",
            "name": "Platform Admin",
        },
    )


@beartype
async def _seed_test_brand_user(session: AsyncSession) -> None:
    brand_result = await session.execute(
        sa.text("SELECT id FROM brands WHERE slug = :slug LIMIT 1"),
        {"slug": "test-brand"},
    )
    brand_id = brand_result.scalar_one_or_none()
    if not isinstance(brand_id, UUID):
        raise RuntimeError("Test brand is missing. Run brand seed first.")

    user_result = await session.execute(
        sa.text(
            """
            INSERT INTO users (
                phone,
                email,
                name,
                password_hash,
                is_verified,
                is_admin
            )
            VALUES (
                :phone,
                :email,
                :name,
                :password_hash,
                TRUE,
                FALSE
            )
            ON CONFLICT (phone) DO UPDATE
            SET
                email = EXCLUDED.email,
                name = EXCLUDED.name,
                password_hash = EXCLUDED.password_hash,
                is_verified = TRUE,
                is_admin = FALSE,
                updated_at = now()
            RETURNING id
            """
        ),
        {
            "phone": "+12025550102",
            "email": "brand@example.invalid",
            "name": "Test Brand Owner",
            "password_hash": _hash_password(os.environ["DEMO_BRAND_PASSWORD"]),
        },
    )
    user_id = user_result.scalar_one()
    if not isinstance(user_id, UUID):
        raise RuntimeError("Database returned non-UUID user id.")

    await session.execute(
        sa.text(
            """
            INSERT INTO brand_users (brand_id, user_id, role)
            VALUES (:brand_id, :user_id, 'owner')
            ON CONFLICT (brand_id, user_id) DO UPDATE
            SET role = EXCLUDED.role
            """
        ),
        {"brand_id": brand_id, "user_id": user_id},
    )


@beartype
async def _seed_test_product(session: AsyncSession) -> None:
    brand_result = await session.execute(
        sa.text("SELECT id FROM brands WHERE slug = :slug LIMIT 1"),
        {"slug": "test-brand"},
    )
    brand_id_raw = brand_result.scalar_one_or_none()
    if not isinstance(brand_id_raw, UUID):
        raise RuntimeError("Test brand is missing. Run brand seed first.")

    category_result = await session.execute(
        sa.text("SELECT id FROM categories WHERE slug = :slug LIMIT 1"),
        {"slug": "men-t-shirts"},
    )
    category_id_raw = category_result.scalar_one_or_none()
    if not isinstance(category_id_raw, UUID):
        raise RuntimeError("Seed category 'men-t-shirts' is missing.")

    product_result = await session.execute(
        sa.text(
            """
            INSERT INTO products (
                brand_id,
                category_id,
                name,
                slug,
                description,
                is_active,
                is_new_arrival
            )
            VALUES (
                :brand_id,
                :category_id,
                :name,
                :slug,
                :description,
                :is_active,
                :is_new_arrival
            )
            ON CONFLICT (slug) DO UPDATE
            SET
                brand_id = EXCLUDED.brand_id,
                category_id = EXCLUDED.category_id,
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                is_active = EXCLUDED.is_active,
                is_new_arrival = EXCLUDED.is_new_arrival,
                updated_at = now()
            RETURNING id
            """
        ),
        {
            "brand_id": brand_id_raw,
            "category_id": category_id_raw,
            "name": "Test Hoodie Tee",
            "slug": "test-hoodie-tee",
            "description": "Seeded test product for smoke tests (cart/checkout).",
            "is_active": True,
            "is_new_arrival": True,
        },
    )
    product_id = product_result.scalar_one()
    if not isinstance(product_id, UUID):
        raise RuntimeError("Database returned non-UUID product id.")

    await session.execute(
        sa.text(
            """
            INSERT INTO product_variants (
                product_id,
                size,
                color,
                sku,
                price_rub,
                compare_at_price_rub,
                stock_quantity,
                is_active,
                vendor_code
            )
            VALUES (
                :product_id,
                :size,
                :color,
                :sku,
                :price_rub,
                :compare_at_price_rub,
                :stock_quantity,
                :is_active,
                :vendor_code
            )
            ON CONFLICT (sku) DO UPDATE
            SET
                product_id = EXCLUDED.product_id,
                size = EXCLUDED.size,
                color = EXCLUDED.color,
                price_rub = EXCLUDED.price_rub,
                compare_at_price_rub = EXCLUDED.compare_at_price_rub,
                stock_quantity = EXCLUDED.stock_quantity,
                is_active = EXCLUDED.is_active,
                vendor_code = EXCLUDED.vendor_code
            """
        ),
        {
            "product_id": product_id,
            "size": "M",
            "color": "Black",
            "sku": "TEST-HOODIE-TEE-M-BLK",
            "price_rub": Decimal("7990.00"),
            "compare_at_price_rub": Decimal("9990.00"),
            "stock_quantity": 15,
            "is_active": True,
            "vendor_code": "TEST-VC-001",
        },
    )

    # Keep exactly one deterministic preview image for this seed product.
    await session.execute(
        sa.text("DELETE FROM product_images WHERE product_id = :product_id"),
        {"product_id": product_id},
    )
    await session.execute(
        sa.text(
            """
            INSERT INTO product_images (product_id, url, sort_order, alt_text)
            VALUES (:product_id, :url, :sort_order, :alt_text)
            """
        ),
        {
            "product_id": product_id,
            "url": "http://127.0.0.1:3200/demo-product.svg",
            "sort_order": 0,
            "alt_text": "Test Hoodie Tee",
        },
    )


@beartype
async def seed() -> None:
    if settings.app_env != "development" or urlsplit(settings.database_url).hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise RuntimeError("Demo seed requires a local development database.")
    if not os.environ.get("DEMO_BRAND_PASSWORD"):
        raise RuntimeError("Set DEMO_BRAND_PASSWORD before seeding fictional local data.")
    async with async_session_factory() as session, session.begin():
        for root in CATEGORY_TREE:
            await _seed_category_tree(session, node=root, parent_id=None)
        await _seed_platform_settings(session)
        await _seed_admin_user(session)
        await _seed_test_brand(session)
        await _seed_test_brand_user(session)
        await _seed_test_product(session)

    print("Seed completed successfully.")


@beartype
def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
