from __future__ import annotations

from beartype import beartype

from app.core.config import settings
from app.integrations.email.protocol import EmailProvider
from app.integrations.email.unisender_provider import UnisenderProvider


@beartype
def get_email_provider() -> EmailProvider:
    return UnisenderProvider(
        api_key=settings.unisender_api_key,
        base_url=settings.unisender_base_url,
        sender_email=settings.unisender_sender_email,
        sender_name=settings.unisender_sender_name,
    )
