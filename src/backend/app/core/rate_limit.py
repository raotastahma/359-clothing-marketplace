from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from beartype import beartype
from fastapi import Depends, HTTPException, Request, status
from redis.exceptions import RedisError

from app.core.redis import get_redis

AUTH_RATE_LIMIT_PER_MINUTE = 5
RATE_LIMIT_WINDOW_SECONDS = 60


@runtime_checkable
class RateLimitRedisProtocol(Protocol):
    async def incr(self, name: str) -> int: ...
    async def expire(self, name: str, time: int) -> object: ...


@beartype
async def enforce_auth_rate_limit(
    request: Request,
    redis: RateLimitRedisProtocol = Depends(get_redis),
) -> None:
    client_ip = request.client.host if request.client is not None else "unknown"
    window = datetime.now(UTC).strftime("%Y%m%d%H%M")
    key = f"rate:auth:{client_ip}:{window}"

    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, RATE_LIMIT_WINDOW_SECONDS)
        if count > AUTH_RATE_LIMIT_PER_MINUTE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication requests.",
            )
    except HTTPException:
        raise
    except RedisError:
        return
