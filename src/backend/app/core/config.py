# Application settings loaded from environment / .env via pydantic-settings.
# Single source of runtime configuration for the FastAPI backend; defaults target
# local development, and model validators fail closed when app_env=production
# is combined with insecure values (default JWT secret, localhost/placeholder CORS origins).
from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

INSECURE_JWT_SECRET_KEY = "change-me-in-production"

# Hosts present in the default cors_origins as documentation placeholders.
# They must never reach production: browsers would send credentialed requests
# from whoever actually controls these domains.
PLACEHOLDER_CORS_HOSTS = frozenset({"domain.ru", "brand.domain.ru"})


def _is_non_public_ip_literal(host: str) -> bool:
    """True when host is an IP literal that is not globally routable (loopback, private, link-local)."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Not an IP literal (a DNS name); handled by the explicit host checks instead.
        return False
    return not ip.is_global


class Settings(BaseSettings):
    app_env: str = "development"
    # Debug off by default: it drives SQLAlchemy echo (query logging) and must be
    # opted into explicitly, never accidentally enabled in production.
    app_debug: bool = False
    frontend_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000/api/v1"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/threefivenine"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 30

    s3_endpoint_url: str = "https://s3.twcstorage.ru"
    s3_public_base_url: str = "https://s3.twcstorage.ru"
    s3_region_name: str = "ru-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket_name: str = "threefivenine-media"

    sms_provider_api_key: str = ""
    sms_provider_sender: str = "359"

    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    yookassa_webhook_secret: str = ""
    order_action_token_ttl_hours: int = 72

    yandex_delivery_api_key: str = ""
    yandex_delivery_client_id: str = ""
    yandex_delivery_base_url: str = "https://b2b.taxi.yandex.net/b2b/cargo/integration/v2"

    unisender_api_key: str = ""
    unisender_base_url: str = "https://go1.unisender.ru/ru/transactional/api/v1"
    unisender_sender_email: str = "no-reply@example.invalid"
    unisender_sender_name: str = "359 Marketplace"
    head_of_partnerships_email: str = ""

    otp_length: int = 4
    otp_ttl_seconds: int = 300

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:5173",
            "http://127.0.0.1:3200",
            "http://127.0.0.1:3201",
            "https://domain.ru",
            "https://brand.domain.ru",
        ]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            if value.lstrip().startswith("["):
                return json.loads(value)
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> Settings:
        if self.app_env.strip().lower() != "production":
            return self

        jwt_secret_key = self.jwt_secret_key.strip()
        if jwt_secret_key == "" or jwt_secret_key == INSECURE_JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY must be set to a non-default value in production.")

        return self

    @model_validator(mode="after")
    def _validate_production_cors_origins(self) -> Settings:
        # Fail-closed CORS guard (mirrors the JWT-secret validator above): the API
        # runs with allow_credentials=True, so a localhost or placeholder origin in
        # production would let an attacker-controlled page make credentialed requests.
        if self.app_env.strip().lower() != "production":
            return self

        for origin in self.cors_origins:
            host = (urlsplit(origin).hostname or "").lower()
            if (
                not host
                or host == "localhost"
                or host.endswith(".localhost")
                or host in PLACEHOLDER_CORS_HOSTS
                or _is_non_public_ip_literal(host)
            ):
                raise ValueError(
                    f"CORS origin {origin!r} is not allowed in production; "
                    "set CORS_ORIGINS to the real frontend origins."
                )

        return self

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "enable_decoding": False,
    }


settings = Settings()
