from __future__ import annotations

import logging

import pytest

from app.integrations.sms.dev import DevSmsProvider


@pytest.mark.asyncio
async def test_dev_sms_provider_logs_otp_without_phone(caplog: pytest.LogCaptureFixture) -> None:
    provider = DevSmsProvider()

    with caplog.at_level(logging.INFO, logger="app.integrations.sms.dev"):
        await provider.send_sms(
            phone="+79001234567",
            message="Your 359 verification code: 1234",
        )

    assert "+79001234567" not in caplog.text
    assert "[DEV SMS] Your 359 verification code: 1234" in caplog.text
