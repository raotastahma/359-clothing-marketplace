from __future__ import annotations

import logging

from beartype import beartype

from app.integrations.sms.base import SmsResult

logger = logging.getLogger(__name__)
server_logger = logging.getLogger("uvicorn")


class DevSmsProvider:
    """Logs dev SMS sends for local smoke testing."""

    @beartype
    async def send_sms(self, *, phone: str, message: str) -> SmsResult:
        _ = phone
        logger.info("[DEV SMS] %s", message)
        server_logger.info("[DEV SMS] %s", message)
        return SmsResult(success=True, provider="dev")
