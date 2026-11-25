from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.v1.brand_portal import auth as brand_auth
from app.core.deps import AuthenticatedUser
from app.core.rate_limit import enforce_auth_rate_limit
from app.core.security import create_access_token, create_refresh_token, decode_token


class _MappingResult:
    def __init__(self, row: Mapping[str, object] | None) -> None:
        self._row = row

    def first(self) -> Mapping[str, object] | None:
        return self._row


class _ExecuteResult:
    def __init__(self, row: Mapping[str, object] | None) -> None:
        self._row = row

    def mappings(self) -> _MappingResult:
        return _MappingResult(self._row)


class _FakeSession:
    def __init__(self, row: Mapping[str, object] | None) -> None:
        self._row = row

    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _ExecuteResult:
        _ = statement
        _ = params
        return _ExecuteResult(self._row)


def _brand_row(
    *,
    user_id: UUID | None = None,
    brand_id: UUID | None = None,
    role: str = "manager",
) -> dict[str, object]:
    return {
        "user_id": user_id or uuid4(),
        "password_hash": "hashed-password",
        "brand_id": brand_id or uuid4(),
        "role": role,
        "brand_name": "MASLOV",
        "brand_slug": "maslov",
        "brand_logo_url": None,
        "commission_rate": Decimal("0.3500"),
    }


def _brand_user(*, user_id: UUID) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user_id,
        phone="+79001234567",
        email="manager@maslov.ru",
        name=None,
        is_verified=True,
        scopes=frozenset({"brand"}),
    )


def _password_matches(*, plain_password: str, password_hash: str) -> bool:
    _ = plain_password
    _ = password_hash
    return True


def _password_does_not_match(*, plain_password: str, password_hash: str) -> bool:
    _ = plain_password
    _ = password_hash
    return False


def test_brand_portal_auth_routes_have_rate_limit_dependency() -> None:
    auth_paths = {"/brand-portal/auth/login", "/brand-portal/auth/refresh"}

    for route in brand_auth.router.routes:
        if getattr(route, "path", "") not in auth_paths:
            continue
        dependencies = getattr(route, "dependencies", [])
        assert any(dependency.dependency is enforce_auth_rate_limit for dependency in dependencies)


@pytest.mark.asyncio
async def test_login_returns_brand_scope_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    brand_id = uuid4()
    row = _brand_row(user_id=user_id, brand_id=brand_id, role="manager")
    monkeypatch.setattr(
        brand_auth,
        "_verify_password",
        _password_matches,
    )

    response = await brand_auth.login(
        brand_auth.BrandPortalLoginRequest(
            email="manager@maslov.ru",
            password="correct-password",
        ),
        db=_FakeSession(row),  # type: ignore[arg-type]
    )

    access_payload = decode_token(response.data.access_token)
    refresh_payload = decode_token(response.data.refresh_token)
    assert response.data.brand.id == brand_id
    assert response.data.role == "manager"
    assert access_payload["sub"] == str(user_id)
    assert access_payload["scope"] == "brand"
    assert access_payload["brand_id"] == str(brand_id)
    assert access_payload["role"] == "manager"
    assert refresh_payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_login_raises_401_when_password_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        brand_auth,
        "_verify_password",
        _password_does_not_match,
    )

    with pytest.raises(HTTPException) as exc_info:
        await brand_auth.login(
            brand_auth.BrandPortalLoginRequest(
                email="manager@maslov.ru",
                password="wrong-password",
            ),
            db=_FakeSession(_brand_row()),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_issues_new_tokens_for_brand_refresh_token() -> None:
    user_id = uuid4()
    brand_id = uuid4()
    refresh_token = create_refresh_token(
        user_id=user_id,
        scopes=["brand"],
        extra_claims={"brand_id": str(brand_id), "role": "owner"},
    )

    response = await brand_auth.refresh(
        brand_auth.BrandPortalRefreshRequest(refresh_token=refresh_token),
        db=_FakeSession(_brand_row(user_id=user_id, brand_id=brand_id, role="owner")),  # type: ignore[arg-type]
    )

    access_payload = decode_token(response.data.access_token)
    assert access_payload["sub"] == str(user_id)
    assert access_payload["scope"] == "brand"
    assert access_payload["brand_id"] == str(brand_id)
    assert access_payload["role"] == "owner"


@pytest.mark.asyncio
async def test_refresh_raises_401_without_brand_scope() -> None:
    refresh_token = create_refresh_token(user_id=uuid4(), scopes=["customer"])

    with pytest.raises(HTTPException) as exc_info:
        await brand_auth.refresh(
            brand_auth.BrandPortalRefreshRequest(refresh_token=refresh_token),
            db=_FakeSession(None),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_brand_portal_context_returns_context_for_valid_token() -> None:
    user_id = uuid4()
    brand_id = uuid4()
    access_token = create_access_token(
        user_id=user_id,
        scopes=["brand"],
        extra_claims={"brand_id": str(brand_id), "role": "viewer"},
    )

    context = await brand_auth.get_brand_portal_context(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=access_token),
        current_user=_brand_user(user_id=user_id),
        db=_FakeSession(_brand_row(user_id=user_id, brand_id=brand_id, role="viewer")),
    )

    assert context.user_id == user_id
    assert context.brand_id == brand_id
    assert context.role == "viewer"


@pytest.mark.asyncio
async def test_get_brand_portal_context_raises_401_for_stale_role() -> None:
    user_id = uuid4()
    brand_id = uuid4()
    access_token = create_access_token(
        user_id=user_id,
        scopes=["brand"],
        extra_claims={"brand_id": str(brand_id), "role": "owner"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await brand_auth.get_brand_portal_context(
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=access_token),
            current_user=_brand_user(user_id=user_id),
            db=_FakeSession(_brand_row(user_id=user_id, brand_id=brand_id, role="viewer")),
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_brand_role_raises_403_when_role_is_not_allowed() -> None:
    dependency = brand_auth.require_brand_role("owner", "manager")
    context = brand_auth.BrandPortalContext(
        user_id=uuid4(),
        brand_id=uuid4(),
        brand_name="MASLOV",
        brand_slug="maslov",
        brand_logo_url=None,
        commission_rate=Decimal("0.3500"),
        role="viewer",
    )

    with pytest.raises(HTTPException) as exc_info:
        await dependency(context=context)

    assert exc_info.value.status_code == 403
