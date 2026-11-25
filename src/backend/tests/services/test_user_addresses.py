from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.users import (
    create_my_address,
    delete_my_address,
    list_my_addresses,
    update_my_address,
)
from app.core.deps import AuthenticatedUser
from app.main import app
from app.schemas.user import AddressCreateRequest, AddressUpdateRequest


class _FakeResult:
    def __init__(self, rows: list[Mapping[str, object]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> _FakeResult:
        return self

    def first(self) -> Mapping[str, object] | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Mapping[str, object]]:
        return list(self._rows)


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


def _current_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=uuid4(),
        phone="+79001234567",
        email="user@example.com",
        name="Иван Петров",
        is_verified=True,
        scopes=frozenset({"customer"}),
    )


def _address_row() -> dict[str, object]:
    return {
        "id": uuid4(),
        "city": "Москва",
        "street": "ул. Тверская, 1",
        "apartment": "кв. 10",
        "postal_code": "125009",
        "is_default": True,
        "created_at": datetime.now(UTC),
    }


@pytest.mark.asyncio
async def test_list_addresses_returns_current_user_addresses() -> None:
    db = _FakeDb()
    db.push_response([_address_row()])

    response = await list_my_addresses(current_user=_current_user(), db=cast(AsyncSession, db))

    assert len(response.data) == 1
    assert response.data[0].city == "Москва"


@pytest.mark.asyncio
async def test_create_address_with_default_unsets_previous_defaults() -> None:
    db = _FakeDb()
    db.push_response([])
    db.push_response([_address_row()])

    payload = AddressCreateRequest(
        city="Москва",
        street="ул. Арбат, 5",
        apartment="12",
        postal_code="119019",
        is_default=True,
    )
    response = await create_my_address(
        payload=payload,
        current_user=_current_user(),
        db=cast(AsyncSession, db),
    )

    assert response.data.is_default is True
    assert db.committed is True
    assert len(db.calls) == 2
    assert "UPDATE addresses" in db.calls[0][0]
    assert "INSERT INTO addresses" in db.calls[1][0]


@pytest.mark.asyncio
async def test_create_address_without_default_skips_unset_previous_defaults() -> None:
    db = _FakeDb()
    row = _address_row()
    row["is_default"] = False
    db.push_response([row])

    payload = AddressCreateRequest(
        city="Москва",
        street="ул. Арбат, 5",
        apartment=None,
        postal_code=None,
    )
    response = await create_my_address(
        payload=payload,
        current_user=_current_user(),
        db=cast(AsyncSession, db),
    )

    assert response.data.is_default is False
    assert db.committed is True
    assert len(db.calls) == 1
    assert "INSERT INTO addresses" in db.calls[0][0]


@pytest.mark.asyncio
async def test_update_address_partially_updates_owned_address() -> None:
    db = _FakeDb()
    row = _address_row()
    row["street"] = "ул. Арбат, 8"
    db.push_response([row])

    payload = AddressUpdateRequest(street="ул. Арбат, 8")
    response = await update_my_address(
        address_id=cast(UUID, row["id"]),
        payload=payload,
        current_user=_current_user(),
        db=cast(AsyncSession, db),
    )

    assert response.data.street == "ул. Арбат, 8"
    assert db.committed is True
    assert len(db.calls) == 1
    _, params = db.calls[0]
    assert params is not None
    assert params["street"] == "ул. Арбат, 8"
    assert "city" not in params


@pytest.mark.asyncio
async def test_update_address_with_default_unsets_other_defaults() -> None:
    db = _FakeDb()
    row = _address_row()
    row["is_default"] = True
    db.push_response([])
    db.push_response([row])

    payload = AddressUpdateRequest(is_default=True)
    response = await update_my_address(
        address_id=cast(UUID, row["id"]),
        payload=payload,
        current_user=_current_user(),
        db=cast(AsyncSession, db),
    )

    assert response.data.is_default is True
    assert db.committed is True
    assert len(db.calls) == 2
    assert "UPDATE addresses" in db.calls[0][0]
    assert "id <> :address_id" in db.calls[0][0]


@pytest.mark.asyncio
async def test_update_address_returns_404_for_missing_address() -> None:
    db = _FakeDb()
    payload = AddressUpdateRequest(street="ул. Арбат, 8")

    with pytest.raises(HTTPException) as exc_info:
        await update_my_address(
            address_id=uuid4(),
            payload=payload,
            current_user=_current_user(),
            db=cast(AsyncSession, db),
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_address_deletes_owned_address() -> None:
    db = _FakeDb()
    address_id = uuid4()
    db.push_response([{"id": address_id}])

    response = await delete_my_address(
        address_id=address_id,
        current_user=_current_user(),
        db=cast(AsyncSession, db),
    )

    assert response.data.status == "deleted"
    assert db.committed is True


@pytest.mark.asyncio
async def test_delete_address_returns_404_for_non_owned_address() -> None:
    db = _FakeDb()

    with pytest.raises(HTTPException) as exc_info:
        await delete_my_address(
            address_id=uuid4(),
            current_user=_current_user(),
            db=cast(AsyncSession, db),
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_address_returns_404_for_nonexistent_address() -> None:
    db = _FakeDb()

    with pytest.raises(HTTPException) as exc_info:
        await delete_my_address(
            address_id=uuid4(),
            current_user=_current_user(),
            db=cast(AsyncSession, db),
        )

    assert exc_info.value.status_code == 404


def test_addresses_list_requires_token() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/users/me/addresses")

    assert response.status_code == 401


def test_addresses_create_requires_token() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/users/me/addresses",
            json={"city": "Москва", "street": "ул. Арбат, 5"},
        )

    assert response.status_code == 401


def test_addresses_update_requires_token() -> None:
    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/users/me/addresses/{uuid4()}",
            json={"street": "ул. Арбат, 8"},
        )

    assert response.status_code == 401


def test_addresses_delete_requires_token() -> None:
    with TestClient(app) as client:
        response = client.delete(f"/api/v1/users/me/addresses/{uuid4()}")

    assert response.status_code == 401
