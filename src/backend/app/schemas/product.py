from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta as PaginationMeta

ProductStatusLiteral = Literal["active", "hidden", "archived"]
SortOptionLiteral = Literal["price_asc", "price_desc", "newest"]


class ProductVariantCreateRequest(BaseModel):
    vendor_code: str | None = Field(default=None, max_length=100)
    size: str = Field(min_length=1, max_length=20)
    color: str | None = Field(default=None, max_length=50)
    sku: str = Field(min_length=1, max_length=100)
    price_rub: Decimal = Field(gt=Decimal("0"))
    compare_at_price_rub: Decimal | None = Field(default=None, ge=Decimal("0"))
    stock_quantity: int = Field(default=0, ge=0)
    is_active: bool = True


class ProductVariantUpdateRequest(BaseModel):
    vendor_code: str | None = Field(default=None, max_length=100)
    size: str | None = Field(default=None, min_length=1, max_length=20)
    color: str | None = Field(default=None, max_length=50)
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    price_rub: Decimal | None = Field(default=None, gt=Decimal("0"))
    compare_at_price_rub: Decimal | None = Field(default=None, ge=Decimal("0"))
    stock_quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    fabric_composition: str | None = None
    care_instructions: str | None = None
    brand_id: UUID
    category_id: UUID
    season: str | None = Field(default=None, max_length=50)
    base_price_rub: Decimal | None = Field(default=None, ge=Decimal("0"))
    sale_price_rub: Decimal | None = Field(default=None, ge=Decimal("0"))
    product_status: ProductStatusLiteral = "active"
    is_new_arrival: bool = False
    is_active: bool = True
    variants: list[ProductVariantCreateRequest] = Field(min_length=1)


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    fabric_composition: str | None = None
    care_instructions: str | None = None
    brand_id: UUID | None = None
    category_id: UUID | None = None
    season: str | None = Field(default=None, max_length=50)
    base_price_rub: Decimal | None = Field(default=None, ge=Decimal("0"))
    sale_price_rub: Decimal | None = Field(default=None, ge=Decimal("0"))
    product_status: ProductStatusLiteral | None = None
    is_new_arrival: bool | None = None
    is_active: bool | None = None


class BrandPortalProductCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    fabric_composition: str | None = None
    care_instructions: str | None = None
    category_id: UUID
    season: str | None = Field(default=None, max_length=50)
    base_price_rub: Decimal | None = Field(default=None, ge=Decimal("0"))
    sale_price_rub: Decimal | None = Field(default=None, ge=Decimal("0"))
    product_status: ProductStatusLiteral = "active"
    is_new_arrival: bool = False
    is_active: bool = True
    variants: list[ProductVariantCreateRequest] = Field(min_length=1)


class BrandPortalProductUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    fabric_composition: str | None = None
    care_instructions: str | None = None
    category_id: UUID | None = None
    season: str | None = Field(default=None, max_length=50)
    base_price_rub: Decimal | None = Field(default=None, ge=Decimal("0"))
    sale_price_rub: Decimal | None = Field(default=None, ge=Decimal("0"))
    product_status: ProductStatusLiteral | None = None
    is_new_arrival: bool | None = None
    is_active: bool | None = None


class ProductImageReorderItem(BaseModel):
    image_id: UUID
    sort_order: int = Field(ge=0, le=9)


class ProductImageReorderRequest(BaseModel):
    items: list[ProductImageReorderItem] = Field(min_length=1, max_length=10)


class ProductVariantPayload(BaseModel):
    id: UUID
    vendor_code: str | None
    size: str
    color: str | None
    sku: str
    price_rub: Decimal
    compare_at_price_rub: Decimal | None
    stock_quantity: int
    is_active: bool


class ProductImagePayload(BaseModel):
    id: UUID
    url: str
    sort_order: int
    alt_text: str | None


class BrandMiniPayload(BaseModel):
    id: UUID
    name: str
    slug: str
    logo_url: str | None = None


class CategoryMiniPayload(BaseModel):
    id: UUID
    name: str
    slug: str
    gender: str | None = None
    parent: dict[str, str] | None = None


class ProductDetailPayload(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    fabric_composition: str | None
    care_instructions: str | None
    season: str | None
    base_price_rub: Decimal | None
    sale_price_rub: Decimal | None
    product_status: ProductStatusLiteral
    is_active: bool
    is_new_arrival: bool
    created_at: datetime
    brand: BrandMiniPayload
    category: CategoryMiniPayload
    variants: list[ProductVariantPayload]
    images: list[ProductImagePayload]


class ProductDetailResponse(BaseModel):
    data: ProductDetailPayload


class CatalogProductPayload(BaseModel):
    id: UUID
    name: str
    slug: str
    brand: BrandMiniPayload
    category: CategoryMiniPayload
    price_from: Decimal | None
    compare_at_price_from: Decimal | None
    is_new_arrival: bool
    images: list[ProductImagePayload]
    available_sizes: list[str]


class CatalogProductsResponse(BaseModel):
    data: list[CatalogProductPayload]
    meta: PaginationMeta


class BrandPortalProductsResponse(BaseModel):
    data: list[ProductDetailPayload]
    meta: PaginationMeta


class AdminProductResponse(BaseModel):
    data: ProductDetailPayload


class ProductVariantResponse(BaseModel):
    data: ProductVariantPayload


class ProductVariantsResponse(BaseModel):
    data: list[ProductVariantPayload]


class ProductImagesResponse(BaseModel):
    data: list[ProductImagePayload]


class PublicBrandPayload(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    cover_url: str | None
    products_count: int = 0


class PublicBrandListResponse(BaseModel):
    data: list[PublicBrandPayload]
    meta: PaginationMeta


class PublicBrandDetailResponse(BaseModel):
    data: PublicBrandPayload


class CategoryTreeNode(BaseModel):
    id: UUID
    name: str
    slug: str
    gender: str
    children: list[CategoryTreeNode]


class CategoriesTreeResponse(BaseModel):
    data: list[CategoryTreeNode]


CategoryTreeNode.model_rebuild()
