from __future__ import annotations

import pytest

from app.integrations.email.unisender_provider import UnisenderProvider


@pytest.mark.asyncio
async def test_unisender_provider_returns_mock_id_without_api_key() -> None:
    provider = UnisenderProvider(
        api_key="",
        base_url="https://go1.unisender.ru/ru/transactional/api/v1",
        sender_email="no-reply@example.com",
        sender_name="359 Marketplace",
    )
    message_id = await provider.send_transactional_email(
        to="buyer@example.com",
        template_id="buyer_status_update",
        context={"order_number": "359-1"},
    )
    assert message_id.startswith("mock-unisender-")
