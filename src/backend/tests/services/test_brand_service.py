from __future__ import annotations

from collections.abc import Mapping

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.brand_service import BrandService


class _MappingResult:
    def __init__(self, rows: list[Mapping[str, object]]) -> None:
        self._rows = rows

    def all(self) -> list[Mapping[str, object]]:
        return self._rows

    def first(self) -> Mapping[str, object] | None:
        return self._rows[0] if self._rows else None


class _Result:
    def __init__(self, rows: list[Mapping[str, object]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> _MappingResult:
        return _MappingResult(self._rows)

    def scalar_one_or_none(self) -> object | None:
        return self._rows[0]["value"] if self._rows else None


class _ListBrandsDb(AsyncSession):
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[Mapping[str, object] | None] = []

    async def execute(  # type: ignore[override]
        self,
        statement: sa.TextClause,
        params: Mapping[str, object] | None = None,
    ) -> _Result:
        self.statements.append(str(statement))
        self.params.append(params)
        if len(self.statements) == 1:
            return _Result()
        return _Result([{"total": 0}])


class _SlugDb(AsyncSession):
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[Mapping[str, object] | None] = []

    async def execute(  # type: ignore[override]
        self,
        statement: sa.TextClause,
        params: Mapping[str, object] | None = None,
    ) -> _Result:
        self.statements.append(str(statement))
        self.params.append(params)
        return _Result()


def _normalize_sql(statement: str) -> str:
    return " ".join(statement.split())


@pytest.mark.asyncio
async def test_list_brands_without_is_active_omits_nullable_sql_parameter() -> None:
    db = _ListBrandsDb()
    service = BrandService(db=db)

    brands, total = await service.list_brands(page=1, per_page=20, is_active=None)

    assert brands == []
    assert total == 0
    assert db.params == [{"limit": 20, "offset": 0}, {}]
    for statement in db.statements:
        assert ":is_active" not in statement


@pytest.mark.asyncio
async def test_slug_lookup_for_create_omits_exclude_brand_id() -> None:
    db = _SlugDb()
    service = BrandService(db=db)

    exists = await service._slug_exists(slug="qa-slug")

    assert exists is False
    assert "WHERE slug = :slug LIMIT 1" in _normalize_sql(db.statements[0])
    assert "exclude_brand_id" not in db.statements[0]
    assert db.params == [{"slug": "qa-slug"}]
