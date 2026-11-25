from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from typing import cast

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import redis_client
from app.services.order_action_service import (
    DatabaseSessionProtocol,
    InvalidTokenError,
    OrderActionService,
    TokenGoneError,
)
from app.services.order_service import InvalidTransitionError

router = APIRouter(prefix="/orders/actions", tags=["order-actions"])


@router.get("/{token}/confirm", response_class=HTMLResponse)
async def confirm_order_action(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    await _enforce_rate_limit(request=request, token=token)
    service = OrderActionService(db=cast(DatabaseSessionProtocol, db))
    try:
        result = await service.confirm(token=token)
    except TokenGoneError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    return HTMLResponse(content=_render_html(title=result.title, message=result.message))


@router.get("/{token}/cancel", response_class=HTMLResponse)
async def cancel_order_action(
    token: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    await _enforce_rate_limit(request=request, token=token)
    service = OrderActionService(db=cast(DatabaseSessionProtocol, db))
    try:
        result = await service.cancel(token=token)
    except TokenGoneError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    return HTMLResponse(content=_render_html(title=result.title, message=result.message))


@router.get("/{token}/ship", response_class=HTMLResponse)
async def ship_order_action_form(
    token: str,
    tracking_number: str | None = Query(default=None, alias="tracking_number"),
) -> HTMLResponse:
    return HTMLResponse(
        content=_render_ship_form_html(token=token, tracking_number=tracking_number)
    )


@router.post("/{token}/ship", response_class=HTMLResponse)
async def ship_order_action(
    token: str,
    request: Request,
    tracking_number_form: str | None = Form(default=None, alias="tracking_number"),
    tracking_number_query: str | None = Query(default=None, alias="tracking_number"),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    await _enforce_rate_limit(request=request, token=token)
    tracking_number = await _tracking_number_from_request(
        request=request,
        form_value=tracking_number_form,
        query_value=tracking_number_query,
    )
    if not tracking_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tracking_number is required.",
        )

    service = OrderActionService(db=cast(DatabaseSessionProtocol, db))
    try:
        result = await service.ship(token=token, tracking_number=tracking_number)
    except TokenGoneError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    return HTMLResponse(content=_render_html(title=result.title, message=result.message))


async def _tracking_number_from_request(
    *,
    request: Request,
    form_value: str | None,
    query_value: str | None,
) -> str:
    tracking_number = (form_value or query_value or "").strip()
    if tracking_number:
        return tracking_number

    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        return ""

    payload = await request.json()
    if not isinstance(payload, dict):
        return ""
    payload = cast(dict[str, object], payload)
    value = payload.get("tracking_number")
    if value is None:
        return ""
    return str(value).strip()


async def _enforce_rate_limit(*, request: Request, token: str) -> None:
    client_ip = request.client.host if request.client is not None else "unknown"
    window = datetime.now(UTC).strftime("%Y%m%d%H%M")
    key = f"rate:order-actions:{client_ip}:{token}:{window}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 60)
        if int(count) > 20:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests for this action token.",
            )
    except HTTPException:
        raise
    except Exception:
        # Non-blocking fallback for local/dev mode without Redis.
        return


def _render_html(*, title: str, message: str) -> str:
    safe_title = title.strip() or "Order action"
    safe_message = message.strip() or "Action completed."
    return (
        "<!doctype html>"
        "<html><head><meta charset='utf-8'><title>"
        f"{safe_title}"
        "</title>"
        "<style>body{font-family:Arial,sans-serif;padding:24px;max-width:640px;margin:0 auto;}"
        "h1{margin-bottom:12px;}p{line-height:1.45;color:#333;}</style>"
        "</head><body>"
        f"<h1>{safe_title}</h1><p>{safe_message}</p>"
        "</body></html>"
    )


def _render_ship_form_html(*, token: str, tracking_number: str | None = None) -> str:
    safe_token = escape(token, quote=True)
    safe_tracking_number = escape((tracking_number or "").strip(), quote=True)
    return (
        "<!doctype html>"
        "<html><head><meta charset='utf-8'><title>Ship order</title>"
        "<style>body{font-family:Arial,sans-serif;padding:24px;max-width:640px;margin:0 auto;}"
        "form{display:grid;gap:12px;max-width:420px;}label{font-weight:600;}"
        "input,button{font:inherit;padding:10px 12px;}button{cursor:pointer;}</style>"
        "</head><body>"
        "<h1>Отправить заказ</h1>"
        "<p>Введите трек-номер, чтобы завершить действие по токену.</p>"
        f"<form method='post' action='/api/v1/orders/actions/{safe_token}/ship'>"
        "<label for='tracking_number'>Tracking number</label>"
        f"<input id='tracking_number' name='tracking_number' value='{safe_tracking_number}' "
        "placeholder='YD-123456789' required />"
        "<button type='submit'>Отправить заказ</button>"
        "</form>"
        "</body></html>"
    )
