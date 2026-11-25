from __future__ import annotations

import pytest
from beartype import beartype

from app.core.config import settings
from scripts.seed import seed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("environment", "database"),
    [
        ("production", "postgresql+asyncpg://demo:demo@127.0.0.1/demo"),
        ("development", "postgresql+asyncpg://demo:demo@database.example.invalid/demo"),
    ],
)
@beartype
async def test_demo_seed_rejects_nonlocal_or_production_database(
    monkeypatch: pytest.MonkeyPatch, environment: str, database: str
) -> None:
    monkeypatch.setattr(settings, "app_env", environment)
    monkeypatch.setattr(settings, "database_url", database)
    with pytest.raises(RuntimeError, match="local development database"):
        await seed()


@pytest.mark.asyncio
@beartype
async def test_demo_seed_requires_explicit_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "database_url", "postgresql+asyncpg://demo:demo@127.0.0.1/demo")
    monkeypatch.delenv("DEMO_BRAND_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="DEMO_BRAND_PASSWORD"):
        await seed()
