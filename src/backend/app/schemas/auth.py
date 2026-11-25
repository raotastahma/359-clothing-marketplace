from __future__ import annotations

from pydantic import BaseModel, Field


class SendCodeRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+\d{10,15}$", examples=["+79001234567"])


class SendCodeData(BaseModel):
    message: str = "Code sent"
    expires_in: int


class SendCodeResponse(BaseModel):
    data: SendCodeData


class VerifyCodeRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+\d{10,15}$", examples=["+79001234567"])
    code: str = Field(..., min_length=4, max_length=6, examples=["1234"])


class UserData(BaseModel):
    id: str
    phone: str
    name: str | None
    email: str | None
    is_verified: bool


class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserData


class VerifyCodeResponse(BaseModel):
    data: TokenData


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshData(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class RefreshResponse(BaseModel):
    data: RefreshData
