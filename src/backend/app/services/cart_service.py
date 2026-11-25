from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, cast, runtime_checkable
from uuid import UUID

import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable


@dataclass(frozen=True, slots=True)
class InsufficientStockError(ValueError):
    requested: int
    available: int

    @property
    def message(self) -> str:
        return (
            "Insufficient stock for requested quantity: "
            f"requested={self.requested}, available={self.available}"
        )


class CartItemNotFoundError(ValueError):
    pass


@runtime_checkable
class MappingResultProtocol(Protocol):
    def first(self) -> Mapping[str, object] | None: ...

    def all(self) -> list[Mapping[str, object]]: ...


@runtime_checkable
class ExecuteResultProtocol(Protocol):
    def mappings(self) -> MappingResultProtocol: ...


@runtime_checkable
class DatabaseSessionProtocol(Protocol):
    async def execute(
        self,
        statement: Executable,
        params: Mapping[str, object] | None = None,
    ) -> ExecuteResultProtocol: ...

    async def commit(self) -> None: ...


@beartype
def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError("Expected integer-compatible value.")


@beartype
def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(str(value))
    raise TypeError("Expected decimal-compatible value.")


class CartService:
    @beartype
    def __init__(self, *, db: DatabaseSessionProtocol) -> None:
        self._db = db

    @beartype
    async def get_cart(self, *, user_id: UUID) -> dict[str, object]:
        rows = await self._fetch_cart_rows(user_id=user_id)
        return self._build_cart_payload(rows=rows)

    @beartype
    async def add_item(
        self,
        *,
        user_id: UUID,
        product_variant_id: UUID,
        quantity: int,
    ) -> dict[str, object]:
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero.")

        variant = await self._get_variant_snapshot(product_variant_id=product_variant_id)
        existing = await self._db.execute(
            sa.text(
                """
                SELECT id, quantity
                FROM cart_items
                WHERE user_id = :user_id
                  AND product_variant_id = :product_variant_id
                LIMIT 1
                """
            ),
            {"user_id": user_id, "product_variant_id": product_variant_id},
        )
        existing_row = existing.mappings().first()
        existing_qty = _to_int(existing_row["quantity"]) if existing_row is not None else 0
        target_qty = existing_qty + quantity
        self._ensure_stock_available(variant=variant, requested_quantity=target_qty)

        if existing_row is not None:
            await self._db.execute(
                sa.text(
                    """
                    UPDATE cart_items
                    SET quantity = :quantity
                    WHERE id = :cart_item_id
                    """
                ),
                {
                    "quantity": target_qty,
                    "cart_item_id": UUID(str(existing_row["id"])),
                },
            )
        else:
            await self._db.execute(
                sa.text(
                    """
                    INSERT INTO cart_items (user_id, product_variant_id, quantity)
                    VALUES (:user_id, :product_variant_id, :quantity)
                    """
                ),
                {
                    "user_id": user_id,
                    "product_variant_id": product_variant_id,
                    "quantity": quantity,
                },
            )
        await self._db.commit()
        return await self.get_cart(user_id=user_id)

    @beartype
    async def update_item_quantity(
        self,
        *,
        user_id: UUID,
        cart_item_id: UUID,
        quantity: int,
    ) -> dict[str, object]:
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero.")

        cart_item = await self._get_cart_item(user_id=user_id, cart_item_id=cart_item_id)
        variant = await self._get_variant_snapshot(
            product_variant_id=UUID(str(cart_item["product_variant_id"]))
        )
        self._ensure_stock_available(variant=variant, requested_quantity=quantity)

        await self._db.execute(
            sa.text(
                """
                UPDATE cart_items
                SET quantity = :quantity
                WHERE id = :cart_item_id
                  AND user_id = :user_id
                """
            ),
            {"quantity": quantity, "cart_item_id": cart_item_id, "user_id": user_id},
        )
        await self._db.commit()
        return await self.get_cart(user_id=user_id)

    @beartype
    async def remove_item(self, *, user_id: UUID, cart_item_id: UUID) -> dict[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                DELETE FROM cart_items
                WHERE id = :cart_item_id
                  AND user_id = :user_id
                RETURNING id
                """
            ),
            {"cart_item_id": cart_item_id, "user_id": user_id},
        )
        if result.mappings().first() is None:
            raise CartItemNotFoundError("Cart item not found.")
        await self._db.commit()
        return await self.get_cart(user_id=user_id)

    @beartype
    async def _get_cart_item(self, *, user_id: UUID, cart_item_id: UUID) -> Mapping[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT id, product_variant_id, quantity
                FROM cart_items
                WHERE id = :cart_item_id
                  AND user_id = :user_id
                LIMIT 1
                """
            ),
            {"cart_item_id": cart_item_id, "user_id": user_id},
        )
        row = result.mappings().first()
        if row is None:
            raise CartItemNotFoundError("Cart item not found.")
        return row

    @beartype
    async def _get_variant_snapshot(self, *, product_variant_id: UUID) -> Mapping[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    pv.id,
                    pv.stock_quantity,
                    pv.is_active AS variant_is_active,
                    p.is_active AS product_is_active,
                    b.is_active AS brand_is_active
                FROM product_variants pv
                JOIN products p ON p.id = pv.product_id
                JOIN brands b ON b.id = p.brand_id
                WHERE pv.id = :product_variant_id
                LIMIT 1
                """
            ),
            {"product_variant_id": product_variant_id},
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError("Product variant not found.")
        return row

    @beartype
    def _ensure_stock_available(
        self,
        *,
        variant: Mapping[str, object],
        requested_quantity: int,
    ) -> None:
        variant_active = bool(variant["variant_is_active"])
        product_active = bool(variant["product_is_active"])
        brand_active = bool(variant["brand_is_active"])
        if not variant_active or not product_active or not brand_active:
            raise ValueError("Product variant is unavailable.")

        available_quantity = _to_int(variant["stock_quantity"])
        if requested_quantity > available_quantity:
            raise InsufficientStockError(
                requested=requested_quantity,
                available=available_quantity,
            )

    @beartype
    async def _fetch_cart_rows(self, *, user_id: UUID) -> list[Mapping[str, object]]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT
                    ci.id AS cart_item_id,
                    ci.quantity,
                    pv.id AS variant_id,
                    pv.product_id,
                    p.name AS product_name,
                    p.slug AS product_slug,
                    pv.vendor_code,
                    pv.sku,
                    pv.size,
                    pv.color,
                    pv.price_rub,
                    pv.compare_at_price_rub,
                    pv.stock_quantity,
                    b.name AS brand_name,
                    (
                        SELECT pi.url
                        FROM product_images pi
                        WHERE pi.product_id = p.id
                        ORDER BY pi.sort_order ASC, pi.id ASC
                        LIMIT 1
                    ) AS image_url
                FROM cart_items ci
                JOIN product_variants pv ON pv.id = ci.product_variant_id
                JOIN products p ON p.id = pv.product_id
                JOIN brands b ON b.id = p.brand_id
                WHERE ci.user_id = :user_id
                ORDER BY ci.created_at ASC, ci.id ASC
                """
            ),
            {"user_id": user_id},
        )
        return result.mappings().all()

    @beartype
    def _build_cart_payload(self, *, rows: list[Mapping[str, object]]) -> dict[str, object]:
        items: list[dict[str, object]] = []
        total = Decimal("0.00")
        items_count = 0

        for row in rows:
            quantity = _to_int(row["quantity"])
            price = _to_decimal(row["price_rub"])
            total += (price * Decimal(quantity)).quantize(Decimal("0.01"))
            items_count += quantity
            items.append(
                {
                    "id": UUID(str(row["cart_item_id"])),
                    "quantity": quantity,
                    "product_variant": {
                        "id": UUID(str(row["variant_id"])),
                        "product_id": UUID(str(row["product_id"])),
                        "product_name": str(row["product_name"]),
                        "product_slug": str(row["product_slug"]),
                        "vendor_code": cast(str | None, row["vendor_code"]),
                        "sku": str(row["sku"]),
                        "size": str(row["size"]),
                        "color": cast(str | None, row["color"]),
                        "price_rub": price,
                        "compare_at_price_rub": cast(Decimal | None, row["compare_at_price_rub"]),
                        "stock_quantity": _to_int(row["stock_quantity"]),
                        "brand_name": str(row["brand_name"]),
                        "image_url": cast(str | None, row["image_url"]),
                    },
                }
            )

        return {
            "items": items,
            "total": total.quantize(Decimal("0.01")),
            "items_count": items_count,
        }
