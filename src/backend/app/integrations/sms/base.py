from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SmsResult:
    success: bool
    provider: str
    message_id: str | None = None


@runtime_checkable
class SmsProvider(Protocol):
    async def send_sms(self, *, phone: str, message: str) -> SmsResult: ...
