from __future__ import annotations

# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false
import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, cast, runtime_checkable
from uuid import UUID

from beartype import beartype

from app.core.redis import redis_client


@runtime_checkable
class RedisProtocol(Protocol):
    async def get(self, name: str) -> str | None: ...

    async def setex(self, name: str, time: int, value: str) -> object: ...

    async def keys(self, pattern: str) -> list[str]: ...

    async def delete(self, *names: str) -> object: ...


@beartype
def _normalize_for_json(value: object) -> object:
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            normalized[str(key)] = _normalize_for_json(item)
        return normalized
    if isinstance(value, list):
        return [_normalize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_for_json(item) for item in value]
    if isinstance(value, (datetime, date, Decimal, UUID)):
        return str(value)
    return value


class CacheService:
    @beartype
    def __init__(self, *, redis: RedisProtocol | None = None) -> None:
        self._redis = redis or cast(RedisProtocol, redis_client)

    @beartype
    async def get_json(self, *, key: str) -> object | None:
        payload = await self._redis.get(key)
        if payload is None:
            return None
        return cast(object, json.loads(payload))

    @beartype
    async def set_json(self, *, key: str, ttl_seconds: int, value: object) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive.")
        normalized = _normalize_for_json(value)
        serialized = json.dumps(normalized, separators=(",", ":"))
        await self._redis.setex(key, ttl_seconds, serialized)

    @beartype
    async def delete_by_prefix(self, *, prefix: str) -> int:
        keys = await self._redis.keys(f"{prefix}*")
        if not keys:
            return 0
        await self._redis.delete(*keys)
        return len(keys)

    @beartype
    def hashed_key(self, *, prefix: str, payload: Mapping[str, object]) -> str:
        normalized = _normalize_for_json(payload)
        body = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}"
