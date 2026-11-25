from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import enforce_auth_rate_limit
from app.core.redis import get_redis
from app.integrations.sms.base import SmsResult
from app.integrations.sms.dev import DevSmsProvider
from app.schemas.auth import (
    RefreshRequest,
    RefreshResponse,
    SendCodeRequest,
    SendCodeResponse,
    VerifyCodeRequest,
    VerifyCodeResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    dependencies=[Depends(enforce_auth_rate_limit)],
)


class _RefreshOnlySmsProvider:
    async def send_sms(self, *, phone: str, message: str) -> SmsResult:
        _ = phone
        _ = message
        raise RuntimeError("SMS provider is not available for token refresh.")


def _build_auth_service(
    db: AsyncSession,
    redis: Redis,
) -> AuthService:
    if settings.app_env.strip().lower() == "production":
        raise RuntimeError("SMS provider is not configured for production auth.")

    sms_provider = DevSmsProvider()
    return AuthService(
        db=db,  # type: ignore[arg-type]
        redis=redis,  # type: ignore[arg-type]
        sms_provider=sms_provider,
    )


def _build_refresh_auth_service(
    db: AsyncSession,
    redis: Redis,
) -> AuthService:
    return AuthService(
        db=db,  # type: ignore[arg-type]
        redis=redis,  # type: ignore[arg-type]
        sms_provider=_RefreshOnlySmsProvider(),
    )


@router.post("/send-code", response_model=SendCodeResponse)
async def send_code(
    body: SendCodeRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> SendCodeResponse:
    auth_service = _build_auth_service(db, redis)

    try:
        data = await auth_service.send_code(phone=body.phone)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    expires_in = data.get("expires_in")
    if not isinstance(expires_in, int):
        expires_in = settings.otp_ttl_seconds

    message = data.get("message")
    if not isinstance(message, str):
        message = "Code sent"

    return SendCodeResponse(
        data={"message": message, "expires_in": expires_in},  # type: ignore[arg-type]
    )


@router.post("/verify-code", response_model=VerifyCodeResponse)
async def verify_code(
    body: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> VerifyCodeResponse:
    auth_service = _build_auth_service(db, redis)

    try:
        result = await auth_service.verify_code(phone=body.phone, code=body.code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    user_raw = result.get("user")
    if not isinstance(user_raw, dict):
        raise HTTPException(status_code=500, detail="Internal error.")

    return VerifyCodeResponse(
        data={  # type: ignore[arg-type]
            "access_token": str(result.get("access_token", "")),
            "refresh_token": str(result.get("refresh_token", "")),
            "token_type": str(result.get("token_type", "bearer")),
            "expires_in": int(str(result.get("expires_in", 1800))),
            "user": {
                "id": str(user_raw.get("id", "")),
                "phone": str(user_raw.get("phone", "")),
                "name": user_raw.get("name"),
                "email": user_raw.get("email"),
                "is_verified": bool(user_raw.get("is_verified", True)),
            },
        },
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RefreshResponse:
    auth_service = _build_refresh_auth_service(db, redis)

    try:
        result = await auth_service.refresh_tokens(refresh_token=body.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return RefreshResponse(
        data={  # type: ignore[arg-type]
            "access_token": str(result.get("access_token", "")),
            "refresh_token": str(result.get("refresh_token", "")),
            "expires_in": int(str(result.get("expires_in", 1800))),
        },
    )
