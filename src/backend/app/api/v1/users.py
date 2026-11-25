from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthenticatedUser, require_scope
from app.schemas.product import (
    BrandMiniPayload,
    CatalogProductPayload,
    CatalogProductsResponse,
    CategoryMiniPayload,
    PaginationMeta,
    ProductImagePayload,
)
from app.schemas.user import (
    AddressCreateRequest,
    AddressListResponse,
    AddressPayload,
    AddressResponse,
    AddressUpdateRequest,
    DeleteStatusPayload,
    DeleteStatusResponse,
    UserProfilePayload,
    UserProfileResponse,
    UserProfileUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["users"])


def _to_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        return UUID(value)
    raise ValueError("Invalid UUID value.")


def _to_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    raise ValueError("Invalid datetime value.")


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError("Invalid boolean value.")


def _to_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ValueError("Invalid optional string value.")


def _to_str(value: object) -> str:
    if isinstance(value, str):
        return value
    raise ValueError("Invalid string value.")


def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError("Invalid integer value.")


def _to_optional_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | str):
        return Decimal(str(value))
    raise ValueError("Invalid decimal value.")


def _to_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in cast(list[object], value) if item is not None]
    if isinstance(value, tuple):
        return [str(item) for item in cast(tuple[object, ...], value) if item is not None]
    return [str(value)]


def _user_profile_from_row(row: Mapping[str, object]) -> UserProfilePayload:
    return UserProfilePayload(
        id=_to_uuid(row["id"]),
        phone=_to_str(row["phone"]),
        email=_to_optional_str(row["email"]),
        name=_to_optional_str(row["name"]),
        is_verified=_to_bool(row["is_verified"]),
        created_at=_to_datetime(row["created_at"]),
    )


def _address_from_row(row: Mapping[str, object]) -> AddressPayload:
    return AddressPayload(
        id=_to_uuid(row["id"]),
        city=_to_str(row["city"]),
        street=_to_str(row["street"]),
        apartment=_to_optional_str(row["apartment"]),
        postal_code=_to_optional_str(row["postal_code"]),
        is_default=_to_bool(row["is_default"]),
        created_at=_to_datetime(row["created_at"]),
    )


def _catalog_product_from_row(row: Mapping[str, object]) -> CatalogProductPayload:
    primary_image = row["primary_image"]
    images: list[ProductImagePayload] = []
    if isinstance(primary_image, dict):
        image = cast(Mapping[str, object], primary_image)
        images.append(
            ProductImagePayload(
                id=_to_uuid(image["id"]),
                url=_to_str(image["url"]),
                sort_order=_to_int(image["sort_order"]),
                alt_text=_to_optional_str(image["alt_text"]),
            )
        )

    return CatalogProductPayload(
        id=_to_uuid(row["id"]),
        name=_to_str(row["name"]),
        slug=_to_str(row["slug"]),
        brand=BrandMiniPayload(
            id=_to_uuid(row["brand_id"]),
            name=_to_str(row["brand_name"]),
            slug=_to_str(row["brand_slug"]),
            logo_url=_to_optional_str(row["brand_logo_url"]),
        ),
        category=CategoryMiniPayload(
            id=_to_uuid(row["category_id"]),
            name=_to_str(row["category_name"]),
            slug=_to_str(row["category_slug"]),
            gender=_to_optional_str(row["category_gender"]),
            parent=None,
        ),
        price_from=_to_optional_decimal(row["price_from"]),
        compare_at_price_from=_to_optional_decimal(row["compare_at_price_from"]),
        is_new_arrival=_to_bool(row["is_new_arrival"]),
        images=images,
        available_sizes=_to_str_list(row["available_sizes"]),
    )


async def _fetch_user_profile(*, db: AsyncSession, user_id: UUID) -> Mapping[str, object]:
    result = await db.execute(
        sa.text(
            """
            SELECT id, phone, email, name, is_verified, created_at
            FROM users
            WHERE id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return cast(Mapping[str, object], dict(row))


async def _fetch_address(
    *,
    db: AsyncSession,
    address_id: UUID,
    user_id: UUID,
) -> Mapping[str, object]:
    result = await db.execute(
        sa.text(
            """
            SELECT id, city, street, apartment, postal_code, is_default, created_at
            FROM addresses
            WHERE id = :address_id AND user_id = :user_id
            LIMIT 1
            """
        ),
        {"address_id": address_id, "user_id": user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")
    return cast(Mapping[str, object], dict(row))


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: AuthenticatedUser = Depends(require_scope("customer")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserProfileResponse:
    existing_row = await _fetch_user_profile(db=db, user_id=current_user.id)
    return UserProfileResponse(data=_user_profile_from_row(existing_row))


@router.patch("/me", response_model=UserProfileResponse)
async def update_my_profile(
    payload: UserProfileUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserProfileResponse:
    update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if update_data:
        set_parts = [f"{field} = :{field}" for field in update_data]
        set_parts.append("updated_at = now()")
        params: dict[str, object] = {"user_id": current_user.id, **update_data}
        result = await db.execute(
            sa.text(
                f"""
                UPDATE users
                SET {", ".join(set_parts)}
                WHERE id = :user_id
                RETURNING id, phone, email, name, is_verified, created_at
                """
            ),
            params,
        )
        row = result.mappings().first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        await db.commit()
        return UserProfileResponse(
            data=_user_profile_from_row(cast(Mapping[str, object], dict(row)))
        )

    existing_row = await _fetch_user_profile(db=db, user_id=current_user.id)
    return UserProfileResponse(data=_user_profile_from_row(existing_row))


@router.get("/me/favorites", response_model=CatalogProductsResponse)
async def list_my_favorites(
    current_user: AuthenticatedUser = Depends(require_scope("customer")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> CatalogProductsResponse:
    result = await db.execute(
        sa.text(
            """
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
            FROM favorites f
            JOIN products p ON p.id = f.product_id
            JOIN brands b ON b.id = p.brand_id
            JOIN categories c ON c.id = p.category_id
            WHERE f.user_id = :user_id
              AND p.is_active = TRUE
              AND p.product_status = 'active'
              AND b.is_active = TRUE
            ORDER BY f.created_at DESC
            """
        ),
        {"user_id": current_user.id},
    )
    data = [
        _catalog_product_from_row(cast(Mapping[str, object], dict(row)))
        for row in result.mappings().all()
    ]
    return CatalogProductsResponse(
        data=data,
        meta=PaginationMeta(page=1, per_page=max(len(data), 1), total=len(data)),
    )


@router.post(
    "/me/favorites/{product_id}",
    response_model=DeleteStatusResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_my_favorite(
    product_id: UUID,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DeleteStatusResponse:
    result = await db.execute(
        sa.text(
            """
            SELECT 1
            FROM products p
            JOIN brands b ON b.id = p.brand_id
            WHERE p.id = :product_id
              AND p.is_active = TRUE
              AND p.product_status = 'active'
              AND b.is_active = TRUE
            LIMIT 1
            """
        ),
        {"product_id": product_id},
    )
    if result.mappings().first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    await db.execute(
        sa.text(
            """
            INSERT INTO favorites (user_id, product_id)
            VALUES (:user_id, :product_id)
            ON CONFLICT ON CONSTRAINT uq_favorites_user_product DO NOTHING
            """
        ),
        {"user_id": current_user.id, "product_id": product_id},
    )
    await db.commit()
    return DeleteStatusResponse(data=DeleteStatusPayload(status="created"))


@router.delete("/me/favorites/{product_id}", response_model=DeleteStatusResponse)
async def delete_my_favorite(
    product_id: UUID,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DeleteStatusResponse:
    await db.execute(
        sa.text(
            """
            DELETE FROM favorites
            WHERE product_id = :product_id AND user_id = :user_id
            """
        ),
        {"product_id": product_id, "user_id": current_user.id},
    )
    await db.commit()
    return DeleteStatusResponse(data=DeleteStatusPayload(status="deleted"))


@router.get("/me/addresses", response_model=AddressListResponse)
async def list_my_addresses(
    current_user: AuthenticatedUser = Depends(require_scope("customer")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AddressListResponse:
    result = await db.execute(
        sa.text(
            """
            SELECT id, city, street, apartment, postal_code, is_default, created_at
            FROM addresses
            WHERE user_id = :user_id
            ORDER BY is_default DESC, created_at DESC
            """
        ),
        {"user_id": current_user.id},
    )
    data = [
        _address_from_row(cast(Mapping[str, object], dict(row))) for row in result.mappings().all()
    ]
    return AddressListResponse(data=data)


@router.post("/me/addresses", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_my_address(
    payload: AddressCreateRequest,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AddressResponse:
    if payload.is_default:
        await db.execute(
            sa.text(
                """
                UPDATE addresses
                SET is_default = FALSE
                WHERE user_id = :user_id
                """
            ),
            {"user_id": current_user.id},
        )

    params = payload.model_dump()
    result = await db.execute(
        sa.text(
            """
            INSERT INTO addresses (user_id, city, street, apartment, postal_code, is_default)
            VALUES (:user_id, :city, :street, :apartment, :postal_code, :is_default)
            RETURNING id, city, street, apartment, postal_code, is_default, created_at
            """
        ),
        {"user_id": current_user.id, **params},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Address not created.",
        )
    await db.commit()
    return AddressResponse(data=_address_from_row(cast(Mapping[str, object], dict(row))))


@router.patch("/me/addresses/{address_id}", response_model=AddressResponse)
async def update_my_address(
    address_id: UUID,
    payload: AddressUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> AddressResponse:
    update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not update_data:
        existing_row = await _fetch_address(db=db, address_id=address_id, user_id=current_user.id)
        return AddressResponse(data=_address_from_row(existing_row))

    is_default = update_data.get("is_default")
    if isinstance(is_default, bool) and is_default:
        await db.execute(
            sa.text(
                """
                UPDATE addresses
                SET is_default = FALSE
                WHERE user_id = :user_id AND id <> :address_id
                """
            ),
            {"user_id": current_user.id, "address_id": address_id},
        )

    set_parts = [f"{field} = :{field}" for field in update_data]
    params = {"address_id": address_id, "user_id": current_user.id, **update_data}
    result = await db.execute(
        sa.text(
            f"""
            UPDATE addresses
            SET {", ".join(set_parts)}
            WHERE id = :address_id AND user_id = :user_id
            RETURNING id, city, street, apartment, postal_code, is_default, created_at
            """
        ),
        params,
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")

    await db.commit()
    return AddressResponse(data=_address_from_row(cast(Mapping[str, object], dict(row))))


@router.delete("/me/addresses/{address_id}", response_model=DeleteStatusResponse)
async def delete_my_address(
    address_id: UUID,
    current_user: AuthenticatedUser = Depends(require_scope("customer")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DeleteStatusResponse:
    result = await db.execute(
        sa.text(
            """
            DELETE FROM addresses
            WHERE id = :address_id AND user_id = :user_id
            RETURNING id
            """
        ),
        {"address_id": address_id, "user_id": current_user.id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")

    await db.commit()
    return DeleteStatusResponse(data=DeleteStatusPayload(status="deleted"))
