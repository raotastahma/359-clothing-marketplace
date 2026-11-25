from __future__ import annotations

import httpx
from beartype import beartype

from app.integrations.email.protocol import EmailProvider


class UnisenderProvider(EmailProvider):
    @beartype
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        sender_email: str,
        sender_name: str,
    ) -> None:
        if not sender_email.strip():
            raise ValueError("sender_email is required.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._sender_email = sender_email
        self._sender_name = sender_name

    @beartype
    async def send_transactional_email(
        self,
        *,
        to: str,
        template_id: str,
        context: dict[str, object],
    ) -> str:
        if not self._api_key:
            # Local/dev mode for tests without external API key.
            return f"mock-unisender-{template_id}-{to}"

        payload = {
            "api_key": self._api_key,
            "message": {
                "recipients": [{"email": to}],
                "from_email": self._sender_email,
                "from_name": self._sender_name,
                "template_id": template_id,
                "template_data": context,
            },
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{self._base_url}/email/send.json", json=payload)
            response.raise_for_status()
            body = response.json()

        message_id = str(body.get("result", {}).get("message_id", ""))
        if not message_id:
            raise RuntimeError("Unisender response missing message_id.")
        return message_id
