from __future__ import annotations

import json
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.payment import PaymentWebhookAckPayload, PaymentWebhookAckResponse
from app.services.payment_webhook_service import (
    DatabaseSessionProtocol,
    InvalidWebhookSignatureError,
    PaymentWebhookService,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhook", response_model=PaymentWebhookAckResponse)
async def payments_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PaymentWebhookAckResponse:
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook payload must be a JSON object.",
        )
    typed_payload = cast(dict[str, object], payload)

    service = PaymentWebhookService(db=cast(DatabaseSessionProtocol, db))
    try:
        await service.handle_webhook(
            payload=typed_payload,
            raw_body=raw_body,
            headers={key: value for key, value in request.headers.items()},
        )
    except InvalidWebhookSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PaymentWebhookAckResponse(data=PaymentWebhookAckPayload(status="ok"))
