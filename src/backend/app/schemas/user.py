from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import EMAIL_RE


class UserProfilePayload(BaseModel):
    id: UUID
    phone: str
    email: str | None
    name: str | None
    is_verified: bool
    created_at: datetime


class UserProfileResponse(BaseModel):
    data: UserProfilePayload


class UserProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name cannot be empty.")
        return stripped

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().lower()
        if not EMAIL_RE.match(stripped):
            raise ValueError("Email has invalid format.")
        return stripped


class AddressPayload(BaseModel):
    id: UUID
    city: str
    street: str
    apartment: str | None
    postal_code: str | None
    is_default: bool
    created_at: datetime


class AddressResponse(BaseModel):
    data: AddressPayload


class AddressListResponse(BaseModel):
    data: list[AddressPayload]


class AddressCreateRequest(BaseModel):
    city: str = Field(min_length=1, max_length=255)
    street: str = Field(min_length=1, max_length=500)
    apartment: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    is_default: bool = False


class AddressUpdateRequest(BaseModel):
    city: str | None = Field(default=None, min_length=1, max_length=255)
    street: str | None = Field(default=None, min_length=1, max_length=500)
    apartment: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    is_default: bool | None = None


class DeleteStatusPayload(BaseModel):
    status: str


class DeleteStatusResponse(BaseModel):
    data: DeleteStatusPayload
