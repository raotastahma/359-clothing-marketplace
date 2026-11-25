from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmailProvider(Protocol):
    async def send_transactional_email(
        self,
        *,
        to: str,
        template_id: str,
        context: dict[str, object],
    ) -> str: ...
