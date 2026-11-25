from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.users import get_my_profile, update_my_profile
from app.core.deps import AuthenticatedUser
from app.main import app
from app.schemas.user import UserProfileUpdateRequest


class _FakeResult:
    def __init__(self, rows: list[Mapping[str, object]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> _FakeResult:
        return self

    def first(self) -> Mapping[str, object] | None:
        return self._rows[0] if self._rows else None


class _FakeDb:
    def __init__(self) -> None:
        self._responses: list[_FakeResult] = []
        self.committed = False
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def push_response(self, rows: list[Mapping[str, object]]) -> None:
        self._responses.append(_FakeResult(rows))

    async def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> _FakeResult:
        statement_text = str(statement)
        normalized_params = dict(params) if params is not None else None
        self.calls.append((statement_text, normalized_params))
        if self._responses:
            return self._responses.pop(0)
        return _FakeResult()

    async def commit(self) -> None:
        self.committed = True


def _profile_row() -> dict[str, object]:
    return {
        "id": uuid4(),
        "phone": "+79001234567",
        "email": "user@example.com",
        "name": "Иван Петров",
        "is_verified": True,
        "created_at": datetime.now(UTC),
    }


def _current_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=uuid4(),
        phone="+79001234567",
        email="user@example.com",
        name="Иван Петров",
        is_verified=True,
        scopes=frozenset({"customer"}),
    )


@pytest.mark.asyncio
async def test_get_profile_returns_expected_fields() -> None:
    db = _FakeDb()
    db.push_response([_profile_row()])

    response = await get_my_profile(current_user=_current_user(), db=cast(AsyncSession, db))

    assert response.data.phone == "+79001234567"
    assert response.data.email == "user@example.com"
    assert response.data.name == "Иван Петров"
    assert response.data.is_verified is True


@pytest.mark.asyncio
async def test_patch_profile_updates_only_provided_fields() -> None:
    db = _FakeDb()
    row = _profile_row()
    row["name"] = "Новое Имя"
    db.push_response([row])

    payload = UserProfileUpdateRequest(name="Новое Имя", email=None)
    response = await update_my_profile(
        payload=payload,
        current_user=_current_user(),
        db=cast(AsyncSession, db),
    )

    assert response.data.name == "Новое Имя"
    assert db.committed is True
    assert len(db.calls) == 1
    _, params = db.calls[0]
    assert params is not None
    assert params["name"] == "Новое Имя"
    assert "email" not in params


def test_patch_profile_validates_email_format() -> None:
    with pytest.raises(ValidationError):
        UserProfileUpdateRequest(email="not-an-email")


def test_get_profile_requires_token() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/users/me")

    assert response.status_code == 401


def test_patch_profile_requires_token() -> None:
    with TestClient(app) as client:
        response = client.patch("/api/v1/users/me", json={"name": "Новое Имя"})

    assert response.status_code == 401
