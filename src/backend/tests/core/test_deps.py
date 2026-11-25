from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID, uuid4

import jwt
import pytest
from beartype import beartype
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.deps import AuthenticatedUser, get_current_user, require_scope
from app.core.security import create_refresh_token


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


@beartype
def _make_token(*, user_id: UUID, scopes: tuple[str, ...]) -> str:
    token = jwt.encode(
        {"sub": str(user_id), "scope": " ".join(scopes), "type": "access"},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return str(token)


@pytest.mark.asyncio
async def test_get_current_user_returns_user_when_token_is_valid() -> None:
    user_id = uuid4()
    token = _make_token(user_id=user_id, scopes=("customer", "brand"))
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    fake_session = _FakeSession(
        {
            "id": user_id,
            "phone": "+79001234567",
            "email": "user@example.com",
            "name": "Alex",
            "is_verified": True,
        }
    )

    user = await get_current_user(credentials=credentials, db=fake_session)

    assert user.id == user_id
    assert user.phone == "+79001234567"
    assert user.scopes == frozenset({"customer", "brand"})


@pytest.mark.asyncio
async def test_get_current_user_raises_401_without_credentials() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=None, db=_FakeSession(None))

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_raises_401_for_invalid_token() -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.jwt.token")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=credentials, db=_FakeSession(None))

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_raises_401_for_refresh_token() -> None:
    token = create_refresh_token(user_id=uuid4(), scopes=["customer"])
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=credentials, db=_FakeSession(None))

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_raises_401_when_user_not_found() -> None:
    token = _make_token(user_id=uuid4(), scopes=("customer",))
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=credentials, db=_FakeSession(None))

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_scope_allows_user_with_expected_scope() -> None:
    dependency = require_scope("brand")
    user = AuthenticatedUser(
        id=uuid4(),
        phone="+79001234567",
        email=None,
        name=None,
        is_verified=True,
        scopes=frozenset({"brand"}),
    )

    resolved_user = await dependency(current_user=user)

    assert resolved_user == user


@pytest.mark.asyncio
async def test_require_scope_raises_403_when_scope_missing() -> None:
    dependency = require_scope("admin")
    user = AuthenticatedUser(
        id=uuid4(),
        phone="+79001234567",
        email=None,
        name=None,
        is_verified=True,
        scopes=frozenset({"customer"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        await dependency(current_user=user)

    assert exc_info.value.status_code == 403
