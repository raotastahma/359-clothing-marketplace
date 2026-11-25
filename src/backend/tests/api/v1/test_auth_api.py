from __future__ import annotations

from typing import cast

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1 import auth
from app.core.config import settings
from app.core.rate_limit import enforce_auth_rate_limit
from app.integrations.sms.dev import DevSmsProvider
from app.schemas.auth import RefreshRequest


class _FakeAuthService:
    def __init__(self, *, db: object, redis: object, sms_provider: object) -> None:
        _ = db
        _ = redis
        self.sms_provider = sms_provider

    async def refresh_tokens(self, *, refresh_token: str) -> dict[str, object]:
        assert refresh_token == "refresh-token"
        return {
            "access_token": "access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 1800,
        }


class _FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expires: dict[str, int] = {}

    async def incr(self, name: str) -> int:
        self.counts[name] = self.counts.get(name, 0) + 1
        return self.counts[name]

    async def expire(self, name: str, time: int) -> object:
        self.expires[name] = time
        return True


def _request(*, client_host: str = "203.0.113.10") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/send-code",
            "headers": [],
            "client": (client_host, 12345),
        }
    )


def test_auth_routes_have_rate_limit_dependency() -> None:
    for route in auth.router.routes:
        dependencies = getattr(route, "dependencies", [])
        assert any(dependency.dependency is enforce_auth_rate_limit for dependency in dependencies)


@pytest.mark.asyncio
async def test_auth_rate_limit_rejects_sixth_request_per_minute() -> None:
    redis = _FakeRedis()
    request = _request()

    for _ in range(5):
        await enforce_auth_rate_limit(request=request, redis=redis)

    with pytest.raises(HTTPException) as exc_info:
        await enforce_auth_rate_limit(request=request, redis=redis)

    assert exc_info.value.status_code == 429
    assert list(redis.expires.values()) == [60]


def test_build_auth_service_uses_dev_sms_provider_outside_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(auth, "AuthService", _FakeAuthService)

    service = cast(
        _FakeAuthService,
        auth._build_auth_service(db=object(), redis=object()),  # type: ignore[arg-type]
    )

    assert isinstance(service.sms_provider, DevSmsProvider)


def test_build_auth_service_fails_closed_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(auth, "AuthService", _FakeAuthService)

    with pytest.raises(RuntimeError, match="SMS provider is not configured"):
        auth._build_auth_service(db=object(), redis=object())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_refresh_is_not_blocked_by_sms_provider_guard_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(auth, "AuthService", _FakeAuthService)

    response = await auth.refresh(
        RefreshRequest(refresh_token="refresh-token"),
        db=object(),  # type: ignore[arg-type]
        redis=object(),  # type: ignore[arg-type]
    )

    assert response.data.access_token == "access-token"
    assert response.data.refresh_token == "new-refresh-token"
    assert response.data.expires_in == 1800
