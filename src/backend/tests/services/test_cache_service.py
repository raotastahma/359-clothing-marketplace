from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest

from app.services.cache_service import CacheService


class _FakeRedis:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, name: str) -> str | None:
        return self._data.get(name)

    async def setex(self, name: str, time: int, value: str) -> object:
        _ = time
        self._data[name] = value
        return True

    async def keys(self, pattern: str) -> list[str]:
        prefix = pattern.removesuffix("*")
        return [key for key in self._data if key.startswith(prefix)]

    async def delete(self, *names: str) -> object:
        for name in names:
            self._data.pop(name, None)
        return len(names)


@pytest.mark.asyncio
async def test_set_and_get_json_roundtrip() -> None:
    service = CacheService(redis=_FakeRedis())
    value = {"price": Decimal("10.50"), "created_at": datetime(2026, 2, 23, 10, 0, 0)}

    await service.set_json(key="products:test", ttl_seconds=60, value=value)
    cached = await service.get_json(key="products:test")

    assert isinstance(cached, Mapping)
    cached_map = cast(Mapping[str, object], cached)
    assert cached_map["price"] == "10.50"
    created_at = cached_map["created_at"]
    assert isinstance(created_at, str)
    assert created_at.startswith("2026-02-23")


def test_hashed_key_is_stable_for_same_payload() -> None:
    service = CacheService(redis=_FakeRedis())
    payload = {"id": uuid4(), "name": "Jacket"}

    first = service.hashed_key(prefix="products:list", payload=payload)
    second = service.hashed_key(prefix="products:list", payload=payload)

    assert first == second
    assert first.startswith("products:list:")


@pytest.mark.asyncio
async def test_delete_by_prefix_removes_matching_keys() -> None:
    redis = _FakeRedis()
    service = CacheService(redis=redis)
    await service.set_json(key="products:1", ttl_seconds=60, value={"ok": True})
    await service.set_json(key="products:2", ttl_seconds=60, value={"ok": True})
    await service.set_json(key="brands:1", ttl_seconds=60, value={"ok": True})

    removed = await service.delete_by_prefix(prefix="products:")

    assert removed == 2
    assert await service.get_json(key="products:1") is None
    assert await service.get_json(key="brands:1") is not None
