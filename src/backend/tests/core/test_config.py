# Tests for app.core.config: production fail-closed validators (JWT secret,
# CORS origins) and secure defaults (app_debug, cors_origins).
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import INSECURE_JWT_SECRET_KEY, Settings

# Origins that pass the production CORS validator; used so tests targeting the
# JWT validator are not affected by the local .env CORS_ORIGINS value.
PRODUCTION_CORS_ORIGINS = ["https://store.example.invalid", "https://brand.example.invalid"]


@pytest.mark.parametrize("jwt_secret_key", ["", INSECURE_JWT_SECRET_KEY])
def test_settings_rejects_missing_or_default_jwt_secret_in_production(
    jwt_secret_key: str,
) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY must be set"):
        Settings(
            app_env="production",
            jwt_secret_key=jwt_secret_key,
            cors_origins=PRODUCTION_CORS_ORIGINS,
        )


def test_settings_allows_non_default_jwt_secret_in_production() -> None:
    settings = Settings(
        app_env="production",
        frontend_base_url="https://store.example.invalid",
        api_base_url="https://api.example.invalid/api/v1",
        jwt_secret_key="test-production-secret",
        cors_origins=PRODUCTION_CORS_ORIGINS,
    )

    assert settings.jwt_secret_key == "test-production-secret"
    assert settings.frontend_base_url == "https://store.example.invalid"
    assert settings.api_base_url == "https://api.example.invalid/api/v1"


def test_settings_app_debug_defaults_to_false() -> None:
    # Assert the declared field default directly: instantiating Settings would
    # apply .env/environment sources and hide the insecure-default regression.
    assert Settings.model_fields["app_debug"].default is False


def test_settings_rejects_default_cors_origins_in_production() -> None:
    # Default origins contain localhost and placeholder domains; production
    # must fail closed instead of silently trusting them.
    with pytest.raises(ValidationError, match="CORS origin"):
        Settings.model_validate({"app_env": "production", "jwt_secret_key": "test-secret"})


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://app.localhost",
        "https://domain.ru",
        "https://brand.domain.ru",
        "http://127.0.0.1:3200",
        "http://192.168.1.10:3000",
    ],
)
def test_settings_rejects_local_or_placeholder_cors_origin_in_production(origin: str) -> None:
    with pytest.raises(ValidationError, match="CORS origin"):
        Settings.model_validate(
            {
                "app_env": "production",
                "jwt_secret_key": "test-secret",
                "cors_origins": [origin],
            }
        )


def test_settings_allows_public_cors_origins_in_production() -> None:
    settings = Settings.model_validate(
        {
            "app_env": "production",
            "jwt_secret_key": "test-secret",
            "cors_origins": PRODUCTION_CORS_ORIGINS,
        }
    )

    assert settings.cors_origins == PRODUCTION_CORS_ORIGINS


def test_settings_default_cors_origins_include_playwright_smoke_origins() -> None:
    settings = Settings.model_validate({})

    assert "http://127.0.0.1:3200" in settings.cors_origins
    assert "http://127.0.0.1:3201" in settings.cors_origins


@pytest.mark.parametrize(
    "value",
    [
        "http://127.0.0.1:3200,http://127.0.0.1:3201",
        '["http://127.0.0.1:3200", "http://127.0.0.1:3201"]',
    ],
)
def test_cors_environment_accepts_csv_and_json(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("CORS_ORIGINS", value)
    settings = Settings()
    assert settings.cors_origins == ["http://127.0.0.1:3200", "http://127.0.0.1:3201"]
