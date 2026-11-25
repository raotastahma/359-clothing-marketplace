from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol, cast, runtime_checkable
from uuid import UUID

import bcrypt
import sqlalchemy as sa
from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import Executable

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import AuthenticatedUser, http_bearer, require_scope
from app.core.rate_limit import enforce_auth_rate_limit
from app.core.security import create_access_token, create_refresh_token, decode_token

BrandRole = Literal["owner", "manager", "viewer"]
BRAND_ROLES = frozenset({"owner", "manager", "viewer"})

router = APIRouter(prefix="/brand-portal", tags=["brand-portal:auth"])


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


class BrandPortalLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class BrandPortalRefreshRequest(BaseModel):
    refresh_token: str


class BrandPortalBrandData(BaseModel):
    id: UUID
    name: str
    slug: str


class BrandPortalLoginData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    brand: BrandPortalBrandData
    role: BrandRole


class BrandPortalLoginResponse(BaseModel):
    data: BrandPortalLoginData


class BrandPortalRefreshData(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class BrandPortalRefreshResponse(BaseModel):
    data: BrandPortalRefreshData


class BrandPortalMeBrandData(BaseModel):
    id: UUID
    name: str
    slug: str
    logo_url: str | None
    commission_rate: Decimal


class BrandPortalMeData(BaseModel):
    brand: BrandPortalMeBrandData
    role: BrandRole


class BrandPortalMeResponse(BaseModel):
    data: BrandPortalMeData


@dataclass(frozen=True, slots=True)
class BrandPortalContext:
    user_id: UUID
    brand_id: UUID
    brand_name: str
    brand_slug: str
    brand_logo_url: str | None
    commission_rate: Decimal
    role: BrandRole


@beartype
def _unauthorized(detail: str = "Invalid brand portal credentials.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


@beartype
def _forbidden(detail: str = "Insufficient brand portal role.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


@beartype
def _to_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        return UUID(value)
    raise ValueError("Invalid UUID value.")


@beartype
def _to_str(value: object) -> str:
    if isinstance(value, str):
        return value
    raise ValueError("Invalid string value.")


@beartype
def _to_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ValueError("Invalid optional string value.")


@beartype
def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | str):
        return Decimal(str(value))
    raise ValueError("Invalid decimal value.")


@beartype
def _to_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError("Invalid integer value.")


@beartype
def _to_brand_role(value: object) -> BrandRole:
    if isinstance(value, str) and value in BRAND_ROLES:
        return cast(BrandRole, value)
    raise ValueError("Invalid brand role.")


@beartype
def _extract_scopes(payload: Mapping[str, object]) -> frozenset[str]:
    scope = payload.get("scope")
    if isinstance(scope, str):
        return frozenset(part for part in scope.split(" ") if part)

    scopes = payload.get("scopes")
    if isinstance(scopes, list):
        return frozenset(item for item in cast(list[object], scopes) if isinstance(item, str))
    if isinstance(scopes, str):
        return frozenset(part for part in scopes.split(" ") if part)
    return frozenset()


@beartype
def _verify_password(*, plain_password: str, password_hash: str) -> bool:
    return bool(
        bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    )


@beartype
def _create_brand_tokens(*, user_id: UUID, brand_id: UUID, role: BrandRole) -> dict[str, object]:
    extra_claims: dict[str, object] = {"brand_id": str(brand_id), "role": role}
    return {
        "access_token": create_access_token(
            user_id=user_id,
            scopes=["brand"],
            extra_claims=extra_claims,
        ),
        "refresh_token": create_refresh_token(
            user_id=user_id,
            scopes=["brand"],
            extra_claims=extra_claims,
        ),
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


@beartype
def _context_from_row(*, user_id: UUID, row: Mapping[str, object]) -> BrandPortalContext:
    return BrandPortalContext(
        user_id=user_id,
        brand_id=_to_uuid(row["brand_id"]),
        brand_name=_to_str(row["brand_name"]),
        brand_slug=_to_str(row["brand_slug"]),
        brand_logo_url=_to_optional_str(row["brand_logo_url"]),
        commission_rate=_to_decimal(row["commission_rate"]),
        role=_to_brand_role(row["role"]),
    )


@beartype
async def _fetch_brand_context(
    *,
    db: DatabaseSessionProtocol,
    user_id: UUID,
    brand_id: UUID,
) -> BrandPortalContext:
    result = await db.execute(
        sa.text(
            """
            SELECT
                bu.brand_id,
                bu.role::text AS role,
                b.name AS brand_name,
                b.slug AS brand_slug,
                b.logo_url AS brand_logo_url,
                b.commission_rate
            FROM brand_users bu
            JOIN brands b ON b.id = bu.brand_id
            WHERE bu.user_id = :user_id
              AND bu.brand_id = :brand_id
              AND b.is_active = TRUE
            LIMIT 1
            """
        ),
        {"user_id": user_id, "brand_id": brand_id},
    )
    row = result.mappings().first()
    if row is None:
        raise _unauthorized("Brand membership not found.")
    try:
        return _context_from_row(user_id=user_id, row=row)
    except ValueError as exc:
        raise _unauthorized("Invalid brand membership data.") from exc


@beartype
async def _authenticate_brand_login(
    *,
    db: DatabaseSessionProtocol,
    email: str,
    password: str,
) -> BrandPortalContext:
    result = await db.execute(
        sa.text(
            """
            SELECT
                u.id AS user_id,
                u.password_hash,
                bu.brand_id,
                bu.role::text AS role,
                b.name AS brand_name,
                b.slug AS brand_slug,
                b.logo_url AS brand_logo_url,
                b.commission_rate
            FROM users u
            JOIN brand_users bu ON bu.user_id = u.id
            JOIN brands b ON b.id = bu.brand_id
            WHERE lower(u.email) = lower(:email)
              AND b.is_active = TRUE
            ORDER BY
                CASE bu.role
                    WHEN 'owner' THEN 0
                    WHEN 'manager' THEN 1
                    ELSE 2
                END,
                bu.created_at ASC
            LIMIT 1
            """
        ),
        {"email": email.strip()},
    )
    row = result.mappings().first()
    if row is None:
        raise _unauthorized()

    password_hash = row["password_hash"]
    if not isinstance(password_hash, str):
        raise _unauthorized()
    if not _verify_password(plain_password=password, password_hash=password_hash):
        raise _unauthorized()

    try:
        user_id = _to_uuid(row["user_id"])
        return _context_from_row(user_id=user_id, row=row)
    except ValueError as exc:
        raise _unauthorized("Invalid brand login data.") from exc


@beartype
def _brand_claims_from_payload(payload: Mapping[str, object]) -> tuple[UUID, UUID, BrandRole]:
    if payload.get("type") != "refresh":
        raise _unauthorized("Token is not a refresh token.")
    if "brand" not in _extract_scopes(payload):
        raise _unauthorized("Token missing brand scope.")

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise _unauthorized("Token missing `sub` claim.")
    brand_id = payload.get("brand_id")
    if not isinstance(brand_id, str):
        raise _unauthorized("Token missing `brand_id` claim.")

    try:
        return UUID(subject), UUID(brand_id), _to_brand_role(payload.get("role"))
    except ValueError as exc:
        raise _unauthorized("Invalid brand token claims.") from exc


@beartype
async def get_brand_portal_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    current_user: AuthenticatedUser = Depends(require_scope("brand")),
    db: DatabaseSessionProtocol = Depends(get_db),
) -> BrandPortalContext:
    if "brand" not in current_user.scopes:
        raise _forbidden("Brand scope is required.")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Missing Bearer token.")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise _unauthorized("Could not validate credentials.") from exc

    if payload.get("type") != "access":
        raise _unauthorized("Token is not an access token.")
    if "brand" not in _extract_scopes(payload):
        raise _forbidden("Brand scope is required.")

    brand_id_claim = payload.get("brand_id")
    if not isinstance(brand_id_claim, str):
        raise _unauthorized("Token missing `brand_id` claim.")

    try:
        brand_id = UUID(brand_id_claim)
        token_role = _to_brand_role(payload.get("role"))
    except ValueError as exc:
        raise _unauthorized("Invalid brand token claims.") from exc

    context = await _fetch_brand_context(db=db, user_id=current_user.id, brand_id=brand_id)
    if context.role != token_role:
        raise _unauthorized("Brand token role is stale.")
    return context


@beartype
def require_brand_role(*allowed_roles: BrandRole) -> Callable[..., Awaitable[BrandPortalContext]]:
    normalized = frozenset(allowed_roles)
    if not normalized:
        raise ValueError("At least one brand role is required.")

    async def dependency(
        context: BrandPortalContext = Depends(get_brand_portal_context),
    ) -> BrandPortalContext:
        if context.role not in normalized:
            allowed_text = ", ".join(sorted(normalized))
            raise _forbidden(f"Required brand role: {allowed_text}")
        return context

    return dependency


@router.post(
    "/auth/login",
    response_model=BrandPortalLoginResponse,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def login(
    payload: BrandPortalLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> BrandPortalLoginResponse:
    context = await _authenticate_brand_login(
        db=cast(DatabaseSessionProtocol, db),
        email=payload.email,
        password=payload.password,
    )
    tokens = _create_brand_tokens(
        user_id=context.user_id,
        brand_id=context.brand_id,
        role=context.role,
    )
    return BrandPortalLoginResponse(
        data=BrandPortalLoginData(
            access_token=_to_str(tokens["access_token"]),
            refresh_token=_to_str(tokens["refresh_token"]),
            expires_in=_to_int(tokens["expires_in"]),
            brand=BrandPortalBrandData(
                id=context.brand_id,
                name=context.brand_name,
                slug=context.brand_slug,
            ),
            role=context.role,
        )
    )


@router.post(
    "/auth/refresh",
    response_model=BrandPortalRefreshResponse,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def refresh(
    payload: BrandPortalRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> BrandPortalRefreshResponse:
    try:
        decoded = decode_token(payload.refresh_token)
    except ValueError as exc:
        raise _unauthorized("Could not validate credentials.") from exc

    user_id, brand_id, token_role = _brand_claims_from_payload(decoded)
    context = await _fetch_brand_context(
        db=cast(DatabaseSessionProtocol, db),
        user_id=user_id,
        brand_id=brand_id,
    )
    if context.role != token_role:
        raise _unauthorized("Brand token role is stale.")

    tokens = _create_brand_tokens(
        user_id=context.user_id,
        brand_id=context.brand_id,
        role=context.role,
    )
    return BrandPortalRefreshResponse(
        data=BrandPortalRefreshData(
            access_token=_to_str(tokens["access_token"]),
            refresh_token=_to_str(tokens["refresh_token"]),
            expires_in=_to_int(tokens["expires_in"]),
        )
    )


@router.get("/me", response_model=BrandPortalMeResponse)
async def me(
    context: BrandPortalContext = Depends(get_brand_portal_context),
) -> BrandPortalMeResponse:
    return BrandPortalMeResponse(
        data=BrandPortalMeData(
            brand=BrandPortalMeBrandData(
                id=context.brand_id,
                name=context.brand_name,
                slug=context.brand_slug,
                logo_url=context.brand_logo_url,
                commission_rate=context.commission_rate,
            ),
            role=context.role,
        )
    )
