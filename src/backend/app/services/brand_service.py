from __future__ import annotations

# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
import json
import re
from collections.abc import Mapping
from typing import cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.brand import BrandCreateRequest, BrandUpdateRequest

SLUG_RE = re.compile(r"[^a-z0-9]+")


@beartype
def _to_slug(raw: str) -> str:
    slug = SLUG_RE.sub("-", raw.strip().lower()).strip("-")
    if slug:
        return slug
    return f"brand-{uuid4().hex[:8]}"


@beartype
def _json_to_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        decoded = json.loads(value)
        if isinstance(decoded, list):
            return [str(item) for item in decoded]
    return []


@beartype
def _json_to_dict(value: object) -> dict[str, str] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        normalized: dict[str, str] = {}
        for key, item in value.items():
            normalized[str(key)] = str(item)
        return normalized
    if isinstance(value, str):
        decoded = json.loads(value)
        if isinstance(decoded, dict):
            normalized_from_json: dict[str, str] = {}
            for key, item in decoded.items():
                normalized_from_json[str(key)] = str(item)
            return normalized_from_json
    return None


class BrandService:
    @beartype
    def __init__(self, *, db: AsyncSession) -> None:
        self._db = db

    @beartype
    async def create_brand(self, *, payload: BrandCreateRequest) -> dict[str, object]:
        slug_value = payload.slug or payload.name
        unique_slug = await self._ensure_unique_slug(_to_slug(slug_value))

        result = await self._db.execute(
            sa.text(
                """
                INSERT INTO brands (
                    name,
                    slug,
                    description,
                    logo_url,
                    cover_url,
                    notification_emails,
                    yml_feed_url,
                    yml_sync_schedule,
                    commission_rate,
                    payout_bank_details,
                    is_active
                )
                VALUES (
                    :name,
                    :slug,
                    :description,
                    :logo_url,
                    :cover_url,
                    CAST(:notification_emails AS jsonb),
                    :yml_feed_url,
                    :yml_sync_schedule,
                    :commission_rate,
                    CAST(:payout_bank_details AS jsonb),
                    :is_active
                )
                RETURNING id
                """
            ),
            {
                "name": payload.name,
                "slug": unique_slug,
                "description": payload.description,
                "logo_url": str(payload.logo_url) if payload.logo_url is not None else None,
                "cover_url": str(payload.cover_url) if payload.cover_url is not None else None,
                "notification_emails": json.dumps(payload.notification_emails),
                "yml_feed_url": str(payload.yml_feed_url)
                if payload.yml_feed_url is not None
                else None,
                "yml_sync_schedule": payload.yml_sync_schedule,
                "commission_rate": payload.commission_rate,
                "payout_bank_details": (
                    json.dumps(payload.payout_bank_details)
                    if payload.payout_bank_details is not None
                    else None
                ),
                "is_active": payload.is_active,
            },
        )
        row = result.mappings().first()
        if row is None:
            raise RuntimeError("Failed to create brand.")
        await self._db.commit()

        raw_brand_id = row["id"]
        brand_id = UUID(str(raw_brand_id))
        return await self.get_brand_by_id(brand_id=brand_id)

    @beartype
    async def list_brands(
        self,
        *,
        page: int,
        per_page: int,
        is_active: bool | None,
    ) -> tuple[list[dict[str, object]], int]:
        offset = (page - 1) * per_page
        filter_params: dict[str, object] = {}
        filter_clause = ""
        if is_active is not None:
            filter_clause = "WHERE b.is_active = :is_active"
            filter_params["is_active"] = is_active

        rows_result = await self._db.execute(
            sa.text(
                f"""
                SELECT
                    b.id,
                    b.name,
                    b.slug,
                    b.description,
                    b.logo_url,
                    b.cover_url,
                    b.notification_emails,
                    b.yml_feed_url,
                    b.yml_sync_schedule,
                    b.commission_rate,
                    b.payout_bank_details,
                    b.is_active,
                    b.created_at
                FROM brands b
                {filter_clause}
                ORDER BY b.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {
                **filter_params,
                "limit": per_page,
                "offset": offset,
            },
        )
        rows = rows_result.mappings().all()

        count_result = await self._db.execute(
            sa.text(
                f"""
                SELECT COUNT(*) AS total
                FROM brands b
                {filter_clause}
                """
            ),
            filter_params,
        )
        count_row = count_result.mappings().first()
        total = int(count_row["total"]) if count_row is not None else 0

        data = [self._row_to_brand_payload(cast(Mapping[str, object], row)) for row in rows]
        return data, total

    @beartype
    async def get_brand_by_id(self, *, brand_id: UUID) -> dict[str, object]:
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
                    b.notification_emails,
                    b.yml_feed_url,
                    b.yml_sync_schedule,
                    b.commission_rate,
                    b.payout_bank_details,
                    b.is_active,
                    b.created_at,
                    (
                        SELECT COUNT(*)
                        FROM products p
                        WHERE p.brand_id = b.id
                    ) AS products_count,
                    (
                        SELECT COUNT(*)
                        FROM products p
                        WHERE p.brand_id = b.id
                          AND p.product_status = 'active'
                          AND p.is_active = TRUE
                    ) AS active_products_count,
                    (
                        SELECT COUNT(*)
                        FROM feed_sync_logs l
                        WHERE l.brand_id = b.id
                    ) AS sync_logs_count
                FROM brands b
                WHERE b.id = :brand_id
                LIMIT 1
                """
            ),
            {"brand_id": brand_id},
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("Brand not found.")
        payload = self._row_to_brand_payload(cast(Mapping[str, object], row))
        payload["stats"] = {
            "products_count": int(row["products_count"]),
            "active_products_count": int(row["active_products_count"]),
            "sync_logs_count": int(row["sync_logs_count"]),
        }
        return payload

    @beartype
    async def update_brand(
        self,
        *,
        brand_id: UUID,
        payload: BrandUpdateRequest,
    ) -> dict[str, object]:
        set_parts: list[str] = []
        params: dict[str, object] = {"brand_id": brand_id}

        if payload.name is not None:
            set_parts.append("name = :name")
            params["name"] = payload.name
        if payload.slug is not None:
            unique_slug = await self._ensure_unique_slug(
                _to_slug(payload.slug),
                exclude_brand_id=brand_id,
            )
            set_parts.append("slug = :slug")
            params["slug"] = unique_slug
        if payload.description is not None:
            set_parts.append("description = :description")
            params["description"] = payload.description
        if payload.logo_url is not None:
            set_parts.append("logo_url = :logo_url")
            params["logo_url"] = str(payload.logo_url)
        if payload.cover_url is not None:
            set_parts.append("cover_url = :cover_url")
            params["cover_url"] = str(payload.cover_url)
        if payload.notification_emails is not None:
            set_parts.append("notification_emails = CAST(:notification_emails AS jsonb)")
            params["notification_emails"] = json.dumps(payload.notification_emails)
        if payload.yml_feed_url is not None:
            set_parts.append("yml_feed_url = :yml_feed_url")
            params["yml_feed_url"] = str(payload.yml_feed_url)
        if payload.yml_sync_schedule is not None:
            set_parts.append("yml_sync_schedule = :yml_sync_schedule")
            params["yml_sync_schedule"] = payload.yml_sync_schedule
        if payload.commission_rate is not None:
            set_parts.append("commission_rate = :commission_rate")
            params["commission_rate"] = payload.commission_rate
        if payload.payout_bank_details is not None:
            set_parts.append("payout_bank_details = CAST(:payout_bank_details AS jsonb)")
            params["payout_bank_details"] = json.dumps(payload.payout_bank_details)
        if payload.is_active is not None:
            set_parts.append("is_active = :is_active")
            params["is_active"] = payload.is_active

        if not set_parts:
            return await self.get_brand_by_id(brand_id=brand_id)

        update_query = f"UPDATE brands SET {', '.join(set_parts)} WHERE id = :brand_id"
        await self._db.execute(sa.text(update_query), params)
        await self._db.commit()
        return await self.get_brand_by_id(brand_id=brand_id)

    @beartype
    async def deactivate_brand(self, *, brand_id: UUID) -> dict[str, object]:
        await self._db.execute(
            sa.text("UPDATE brands SET is_active = FALSE WHERE id = :brand_id"),
            {"brand_id": brand_id},
        )
        await self._db.commit()
        return await self.get_brand_by_id(brand_id=brand_id)

    @beartype
    async def _ensure_unique_slug(
        self,
        base_slug: str,
        *,
        exclude_brand_id: UUID | None = None,
    ) -> str:
        candidate = base_slug
        suffix = 2
        while True:
            exists = await self._slug_exists(slug=candidate, exclude_brand_id=exclude_brand_id)
            if not exists:
                return candidate
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

    @beartype
    async def _slug_exists(self, *, slug: str, exclude_brand_id: UUID | None = None) -> bool:
        params: dict[str, object] = {"slug": slug}
        exclude_predicate = ""
        if exclude_brand_id is not None:
            exclude_predicate = "AND id != :exclude_brand_id"
            params["exclude_brand_id"] = exclude_brand_id

        result = await self._db.execute(
            sa.text(
                f"""
                SELECT 1
                FROM brands
                WHERE slug = :slug
                  {exclude_predicate}
                LIMIT 1
                """
            ),
            params,
        )
        return result.scalar_one_or_none() is not None

    @beartype
    def _row_to_brand_payload(self, row: Mapping[str, object]) -> dict[str, object]:
        return {
            "id": UUID(str(row["id"])),
            "name": str(row["name"]),
            "slug": str(row["slug"]),
            "description": cast(str | None, row["description"]),
            "logo_url": cast(str | None, row["logo_url"]),
            "cover_url": cast(str | None, row["cover_url"]),
            "notification_emails": _json_to_list(row["notification_emails"]),
            "yml_feed_url": cast(str | None, row["yml_feed_url"]),
            "yml_sync_schedule": cast(str | None, row["yml_sync_schedule"]),
            "commission_rate": row["commission_rate"],
            "payout_bank_details": _json_to_dict(row["payout_bank_details"]),
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
        }
