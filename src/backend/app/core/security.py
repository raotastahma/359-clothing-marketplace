from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from beartype import beartype
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


@beartype
def create_access_token(
    *,
    user_id: UUID,
    scopes: list[str],
    extra_claims: Mapping[str, object] | None = None,
) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, object] = {
        "sub": str(user_id),
        "scope": " ".join(scopes),
        "exp": expire,
        "type": "access",
    }
    if extra_claims is not None:
        payload.update(dict(extra_claims))
    return str(jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm))


@beartype
def create_refresh_token(
    *,
    user_id: UUID,
    scopes: list[str],
    extra_claims: Mapping[str, object] | None = None,
) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload: dict[str, object] = {
        "sub": str(user_id),
        "scope": " ".join(scopes),
        "exp": expire,
        "type": "refresh",
    }
    if extra_claims is not None:
        payload.update(dict(extra_claims))
    return str(jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm))


@beartype
def decode_token(token: str) -> dict[str, object]:
    """Decode and verify a JWT. Raises ValueError on invalid/expired tokens."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired token.") from exc
    return payload
