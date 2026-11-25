from __future__ import annotations

import secrets
from collections.abc import Mapping
from typing import Protocol, runtime_checkable
from uuid import UUID

import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.integrations.sms.base import SmsProvider

OTP_REDIS_PREFIX = "otp:"


@runtime_checkable
class RedisProtocol(Protocol):
    async def get(self, name: str) -> str | None: ...
    async def setex(self, name: str, time: int, value: str) -> object: ...
    async def delete(self, *names: str) -> object: ...


@runtime_checkable
class ScalarResultProtocol(Protocol):
    def scalar_one_or_none(self) -> object: ...


@runtime_checkable
class MappingRowProtocol(Protocol):
    def first(self) -> Mapping[str, object] | None: ...


@runtime_checkable
class MappingResultProtocol(Protocol):
    def mappings(self) -> MappingRowProtocol: ...
    def scalar_one_or_none(self) -> object: ...


@runtime_checkable
class DbSessionProtocol(Protocol):
    async def execute(
        self,
        statement: Executable,
        params: Mapping[str, object] | None = None,
    ) -> MappingResultProtocol: ...

    async def commit(self) -> None: ...


class AuthService:
    @beartype
    def __init__(
        self,
        *,
        db: DbSessionProtocol,
        redis: RedisProtocol,
        sms_provider: SmsProvider,
    ) -> None:
        self._db = db
        self._redis = redis
        self._sms_provider = sms_provider

    @beartype
    async def send_code(self, *, phone: str) -> dict[str, object]:
        otp = self._generate_otp()
        redis_key = f"{OTP_REDIS_PREFIX}{phone}"
        await self._redis.setex(redis_key, settings.otp_ttl_seconds, otp)

        message = f"Your 359 verification code: {otp}"
        await self._sms_provider.send_sms(phone=phone, message=message)

        return {"message": "Code sent", "expires_in": settings.otp_ttl_seconds}

    @beartype
    async def verify_code(self, *, phone: str, code: str) -> dict[str, object]:
        redis_key = f"{OTP_REDIS_PREFIX}{phone}"
        stored_otp = await self._redis.get(redis_key)

        if stored_otp is None:
            raise ValueError("OTP expired or not found. Request a new code.")

        if not secrets.compare_digest(str(stored_otp), code):
            raise ValueError("Invalid verification code.")

        await self._redis.delete(redis_key)

        user = await self._find_or_create_user(phone=phone)
        await self._db.commit()

        user_id = user["id"]
        if not isinstance(user_id, UUID):
            user_id = UUID(str(user_id))

        scopes = await self._determine_scopes(user_id=user_id)
        brand_claims = await self._get_brand_token_claims(user_id=user_id)

        access_token = create_access_token(
            user_id=user_id,
            scopes=scopes,
            extra_claims=brand_claims,
        )
        refresh_token = create_refresh_token(
            user_id=user_id,
            scopes=scopes,
            extra_claims=brand_claims,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "user": {
                "id": str(user_id),
                "phone": str(user["phone"]),
                "name": user.get("name"),
                "email": user.get("email"),
                "is_verified": True,
            },
        }

    @beartype
    async def refresh_tokens(self, *, refresh_token: str) -> dict[str, object]:
        payload = decode_token(refresh_token)

        token_type = payload.get("type")
        if token_type != "refresh":
            raise ValueError("Token is not a refresh token.")

        sub = payload.get("sub")
        if not isinstance(sub, str):
            raise ValueError("Token missing 'sub' claim.")

        user_id = UUID(sub)

        result = await self._db.execute(
            sa.text("SELECT id FROM users WHERE id = :user_id LIMIT 1"),
            {"user_id": user_id},
        )
        if result.scalar_one_or_none() is None:
            raise ValueError("User not found.")

        scopes = await self._determine_scopes(user_id=user_id)
        brand_claims = await self._get_brand_token_claims(user_id=user_id)

        new_access = create_access_token(
            user_id=user_id,
            scopes=scopes,
            extra_claims=brand_claims,
        )
        new_refresh = create_refresh_token(
            user_id=user_id,
            scopes=scopes,
            extra_claims=brand_claims,
        )

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
        }

    @beartype
    def _generate_otp(self) -> str:
        return "".join(secrets.choice("0123456789") for _ in range(settings.otp_length))

    @beartype
    async def _find_or_create_user(self, *, phone: str) -> dict[str, object]:
        result = await self._db.execute(
            sa.text(
                "SELECT id, phone, email, name, is_verified FROM users WHERE phone = :phone LIMIT 1"
            ),
            {"phone": phone},
        )
        row = result.mappings().first()

        if row is not None:
            row_id = row["id"]
            if not row.get("is_verified"):
                await self._db.execute(
                    sa.text(
                        "UPDATE users SET is_verified = TRUE, updated_at = now() WHERE id = :id"
                    ),
                    {"id": row_id},
                )
            return {
                "id": row_id,
                "phone": row["phone"],
                "email": row.get("email"),
                "name": row.get("name"),
                "is_verified": True,
            }

        insert_result = await self._db.execute(
            sa.text(
                "INSERT INTO users (phone, is_verified) "
                "VALUES (:phone, TRUE) "
                "RETURNING id, phone, email, name, is_verified"
            ),
            {"phone": phone},
        )
        new_row = insert_result.mappings().first()
        if new_row is None:
            raise RuntimeError("Failed to create user.")

        return {
            "id": new_row["id"],
            "phone": new_row["phone"],
            "email": new_row.get("email"),
            "name": new_row.get("name"),
            "is_verified": True,
        }

    @beartype
    async def _determine_scopes(self, *, user_id: UUID) -> list[str]:
        scopes = ["customer"]

        result = await self._db.execute(
            sa.text("SELECT 1 FROM brand_users WHERE user_id = :user_id LIMIT 1"),
            {"user_id": user_id},
        )
        if result.scalar_one_or_none() is not None:
            scopes.append("brand")

        admin_result = await self._db.execute(
            sa.text("SELECT is_admin FROM users WHERE id = :user_id LIMIT 1"),
            {"user_id": user_id},
        )
        if bool(admin_result.scalar_one_or_none()):
            scopes.append("admin")

        return scopes

    @beartype
    async def _get_brand_token_claims(self, *, user_id: UUID) -> dict[str, object]:
        result = await self._db.execute(
            sa.text(
                """
                SELECT brand_id, role::text AS role
                FROM brand_users
                WHERE user_id = :user_id
                ORDER BY
                    CASE role
                        WHEN 'owner' THEN 0
                        WHEN 'manager' THEN 1
                        ELSE 2
                    END,
                    created_at ASC
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        )
        row = result.mappings().first()
        if row is None:
            return {}

        brand_id = row.get("brand_id")
        role = row.get("role")
        if brand_id is None or not isinstance(role, str):
            return {}

        return {"brand_id": str(brand_id), "role": role}
