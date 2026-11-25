from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, cast, runtime_checkable
from uuid import UUID

import jwt
import sqlalchemy as sa
from beartype import beartype
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.sql.base import Executable

from app.core.config import settings
from app.core.database import get_db

SUPPORTED_SCOPES = frozenset({"customer", "brand", "admin"})
http_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: UUID
    phone: str
    email: str | None
    name: str | None
    is_verified: bool
    scopes: frozenset[str]


@runtime_checkable
class MappingResultProtocol(Protocol):
    def first(self) -> Mapping[str, object] | None: ...


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


@beartype
def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )


@beartype
def _extract_scopes(payload: Mapping[str, object]) -> frozenset[str]:
    collected_scopes: set[str] = set()

    scope_claim = payload.get("scope")
    if isinstance(scope_claim, str):
        collected_scopes.update(part for part in scope_claim.split(" ") if part)

    scopes_claim = payload.get("scopes")
    if isinstance(scopes_claim, str):
        collected_scopes.update(part for part in scopes_claim.split(" ") if part)
    elif isinstance(scopes_claim, list):
        for item in cast(list[object], scopes_claim):
            if isinstance(item, str):
                collected_scopes.add(item)

    filtered = {scope for scope in collected_scopes if scope in SUPPORTED_SCOPES}
    return frozenset(filtered)


@beartype
def _decode_token(token: str) -> Mapping[str, object]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise _unauthorized() from exc

    return cast(Mapping[str, object], payload)


@beartype
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: DatabaseSessionProtocol = Depends(get_db),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Missing Bearer token.")

    payload = _decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise _unauthorized("Token is not an access token.")

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise _unauthorized("Token missing `sub` claim.")

    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise _unauthorized("Token `sub` claim must be UUID.") from exc

    result = await db.execute(
        sa.text(
            """
            SELECT id, phone, email, name, is_verified
            FROM users
            WHERE id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise _unauthorized("User not found.")

    row_id = row["id"]
    if isinstance(row_id, UUID):
        resolved_id = row_id
    elif isinstance(row_id, str):
        resolved_id = UUID(row_id)
    else:
        raise _unauthorized("Invalid user id type in database.")

    phone = row["phone"]
    email = row["email"]
    name = row["name"]
    is_verified = row["is_verified"]

    if not isinstance(phone, str):
        raise _unauthorized("Invalid user phone type in database.")
    if email is not None and not isinstance(email, str):
        raise _unauthorized("Invalid user email type in database.")
    if name is not None and not isinstance(name, str):
        raise _unauthorized("Invalid user name type in database.")
    if not isinstance(is_verified, bool):
        raise _unauthorized("Invalid user verification flag type in database.")

    return AuthenticatedUser(
        id=resolved_id,
        phone=phone,
        email=email,
        name=name,
        is_verified=is_verified,
        scopes=_extract_scopes(payload),
    )


@beartype
def require_scope(*required_scopes: str) -> Callable[..., Awaitable[AuthenticatedUser]]:
    normalized = frozenset(scope.strip() for scope in required_scopes if scope.strip())
    if not normalized:
        raise ValueError("At least one scope is required.")

    unsupported = normalized - SUPPORTED_SCOPES
    if unsupported:
        unsupported_str = ", ".join(sorted(unsupported))
        raise ValueError(f"Unsupported scope(s): {unsupported_str}")

    async def dependency(
        current_user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if normalized.isdisjoint(current_user.scopes):
            required_scopes_text = ", ".join(sorted(normalized))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient scope. Required one of: {required_scopes_text}",
            )
        return current_user

    return dependency
