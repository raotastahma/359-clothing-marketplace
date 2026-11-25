from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from beartype import beartype
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from app.schemas.common import EMAIL_RE
from app.schemas.common import PaginationMeta as PaginationMeta


@beartype
def _validate_emails(emails: list[str]) -> list[str]:
    if not emails:
        raise ValueError("notification_emails must contain at least one email.")
    normalized: list[str] = []
    for email in emails:
        candidate = email.strip().lower()
        if not EMAIL_RE.match(candidate):
            raise ValueError(f"Invalid email: {email}")
        normalized.append(candidate)
    return normalized


class BrandCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    logo_url: AnyHttpUrl | None = None
    cover_url: AnyHttpUrl | None = None
    notification_emails: list[str]
    yml_feed_url: AnyHttpUrl | None = None
    yml_sync_schedule: str | None = Field(default="0 */4 * * *", max_length=50)
    commission_rate: Decimal = Field(default=Decimal("0.3500"), ge=Decimal("0"), le=Decimal("1"))
    payout_bank_details: dict[str, str] | None = None
    is_active: bool = True

    @field_validator("notification_emails")
    @classmethod
    def _emails_valid(cls, value: list[str]) -> list[str]:
        return _validate_emails(value)


class BrandUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    logo_url: AnyHttpUrl | None = None
    cover_url: AnyHttpUrl | None = None
    notification_emails: list[str] | None = None
    yml_feed_url: AnyHttpUrl | None = None
    yml_sync_schedule: str | None = Field(default=None, max_length=50)
    commission_rate: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    payout_bank_details: dict[str, str] | None = None
    is_active: bool | None = None

    @field_validator("notification_emails")
    @classmethod
    def _emails_valid(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _validate_emails(value)


class BrandStats(BaseModel):
    products_count: int = 0
    active_products_count: int = 0
    sync_logs_count: int = 0


class BrandPayload(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    cover_url: str | None
    notification_emails: list[str]
    yml_feed_url: str | None
    yml_sync_schedule: str | None
    commission_rate: Decimal
    payout_bank_details: dict[str, str] | None
    is_active: bool
    created_at: datetime
    stats: BrandStats | None = None


class BrandResponse(BaseModel):
    data: BrandPayload


class BrandListResponse(BaseModel):
    data: list[BrandPayload]
    meta: PaginationMeta
