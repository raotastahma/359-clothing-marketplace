from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.users import add_my_favorite, delete_my_favorite, list_my_favorites
from app.core.deps import AuthenticatedUser
from app.main import app


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


def _product_row() -> dict[str, object]:
    return {
        "id": uuid4(),
        "name": "Платье",
        "slug": "dress",
        "is_new_arrival": True,
        "brand_id": uuid4(),
        "brand_name": "Brand",
        "brand_slug": "brand",
        "brand_logo_url": None,
        "category_id": uuid4(),
        "category_name": "Платья",
        "category_slug": "dresses",
        "category_gender": "women",
        "price_from": Decimal("10000"),
        "compare_at_price_from": None,
        "available_sizes": ["S", "M"],
        "primary_image": {
            "id": uuid4(),
            "url": "/dress.jpg",
            "sort_order": 0,
            "alt_text": "Платье",
        },
    }


@pytest.mark.asyncio
async def test_list_favorites_returns_catalog_products() -> None:
    db = _FakeDb()
    db.push_response([_product_row()])

    response = await list_my_favorites(current_user=_current_user(), db=cast(AsyncSession, db))

    assert len(response.data) == 1
    assert response.data[0].slug == "dress"
    assert response.data[0].images[0].url == "/dress.jpg"
    assert response.meta.total == 1


@pytest.mark.asyncio
async def test_add_favorite_inserts_user_product_pair() -> None:
    db = _FakeDb()
    product_id = uuid4()
    db.push_response([{"exists": 1}])

    response = await add_my_favorite(
        product_id=product_id,
        current_user=_current_user(),
        db=cast(AsyncSession, db),
    )

    assert response.data.status == "created"
    assert db.committed is True
    assert len(db.calls) == 2
    assert "INSERT INTO favorites" in db.calls[1][0]
    assert db.calls[1][1] is not None
    assert db.calls[1][1]["product_id"] == product_id


@pytest.mark.asyncio
async def test_add_favorite_returns_404_for_missing_product() -> None:
    db = _FakeDb()

    with pytest.raises(HTTPException) as exc_info:
        await add_my_favorite(
            product_id=uuid4(),
            current_user=_current_user(),
            db=cast(AsyncSession, db),
        )

    assert exc_info.value.status_code == 404
    assert db.committed is False


@pytest.mark.asyncio
async def test_delete_favorite_deletes_current_user_pair() -> None:
    db = _FakeDb()
    product_id = uuid4()

    response = await delete_my_favorite(
        product_id=product_id,
        current_user=_current_user(),
        db=cast(AsyncSession, db),
    )

    assert response.data.status == "deleted"
    assert db.committed is True
    assert "DELETE FROM favorites" in db.calls[0][0]
    assert db.calls[0][1] is not None
    assert db.calls[0][1]["product_id"] == product_id


def test_favorites_list_requires_token() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/users/me/favorites")

    assert response.status_code == 401
