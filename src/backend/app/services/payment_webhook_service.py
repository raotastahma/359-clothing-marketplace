# YooKassa payment webhook handling: verifies webhook signatures, marks payments
# succeeded/refunded, creates fiscal receipts via the YooKassa Receipts API, splits
# paid orders into brand sub-orders, and triggers buyer/brand notifications.
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol, cast, runtime_checkable
from uuid import UUID, uuid4

import httpx
import sqlalchemy as sa
from beartype import beartype
from sqlalchemy.sql.base import Executable

from app.core.config import settings
from app.services.notification_service import ActionTokens, NotificationService
from app.services.order_service import InvalidTransitionError, OrderService

logger = logging.getLogger(__name__)


@beartype
def _to_uuid(value: object) -> UUID:
    return UUID(str(value))


@beartype
def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float, str)):
        return Decimal(str(value))
    raise TypeError("Expected decimal-compatible value.")


class InvalidWebhookSignatureError(ValueError):
    pass


@runtime_checkable
class MappingResultProtocol(Protocol):
    def first(self) -> Mapping[str, object] | None: ...

    def all(self) -> list[Mapping[str, object]]: ...


@runtime_checkable
class ExecuteResultProtocol(Protocol):
    def mappings(self) -> MappingResultProtocol: ...

    def scalar_one_or_none(self) -> object: ...


@runtime_checkable
class DatabaseSessionProtocol(Protocol):
    async def execute(
        self,
        statement: Executable,
        params: Mapping[str, object] | None = None,
    ) -> ExecuteResultProtocol: ...

    async def commit(self) -> None: ...


class PaymentWebhookService:
    @beartype
    def __init__(
        self,
        *,
        db: DatabaseSessionProtocol,
        order_service: OrderService | None = None,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._db = db
        self._order_service = order_service or OrderService(db=db)
        self._notification_service = notification_service or NotificationService()

    @beartype
    async def handle_webhook(
        self,
        *,
        payload: Mapping[str, object],
        raw_body: bytes,
        headers: Mapping[str, str],
    ) -> None:
        self._verify_signature(raw_body=raw_body, headers=headers)

        event = str(payload.get("event", "")).strip()
        obj = payload.get("object")
        if not isinstance(obj, Mapping):
            raise ValueError("Webhook payload missing `object`.")
        object_payload = cast(Mapping[str, object], obj)

        external_payment_id = str(object_payload.get("id", "")).strip()
        if not external_payment_id:
            raise ValueError("Webhook payload missing payment id.")

        payment_row = await self._get_payment_by_external_id(
            external_payment_id=external_payment_id
        )
        if payment_row is None:
            # Unknown payment can happen in noisy environments; keep webhook idempotent-safe.
            return

        if event == "payment.succeeded":
            await self._handle_payment_succeeded(
                payment_row=payment_row,
                payload=payload,
                object_payload=object_payload,
            )
            return
        if event == "payment.cancelled":
            await self._handle_payment_cancelled(payment_row=payment_row, payload=payload)
            return

    @beartype
    async def _handle_payment_succeeded(
        self,
        *,
        payment_row: Mapping[str, object],
        payload: Mapping[str, object],
        object_payload: Mapping[str, object],
    ) -> None:
        current_status = str(payment_row["status"])
        if current_status in {"succeeded", "refunded"}:
            return

        order_id = _to_uuid(payment_row["order_id"])
        await self._db.execute(
            sa.text(
                """
                UPDATE payments
                SET status = 'succeeded',
                    provider_data_json = CAST(:provider_data_json AS jsonb)
                WHERE id = :payment_id
                """
            ),
            {
                "payment_id": _to_uuid(payment_row["id"]),
                "provider_data_json": json.dumps(payload, ensure_ascii=False),
            },
        )

        receipt_url = await self._create_receipt(
            payment_row=payment_row,
            object_payload=object_payload,
            order_id=order_id,
        )
        if receipt_url is not None:
            await self._db.execute(
                sa.text(
                    """
                    UPDATE payments
                    SET receipt_url = :receipt_url
                    WHERE id = :payment_id
                    """
                ),
                {"receipt_url": receipt_url, "payment_id": _to_uuid(payment_row["id"])},
            )

        transitioned_order = await self._order_service.transition_order(
            order_id=order_id,
            target_status="paid",
            notify_buyer=False,
            commit=False,
        )

        paid_at = cast(datetime | None, transitioned_order.get("paid_at")) or datetime.now(UTC)
        sub_orders = await self._order_service.create_sub_orders(order_id=order_id, paid_at=paid_at)
        brand_tokens = await self._ensure_brand_action_tokens(
            order_id=order_id,
            sub_orders=sub_orders,
        )
        order_payload = await self._order_service.get_order_payload_for_notifications(
            order_id=order_id
        )
        order_items = await self._order_service.list_order_items(order_id=order_id)
        brand_emails = await self._order_service.get_brand_notification_emails(order_id=order_id)
        await self._notification_service.notify_order_paid(
            order=order_payload,
            items=order_items,
            brand_notification_emails=brand_emails,
            action_tokens=brand_tokens,
        )
        await self._db.commit()

    @beartype
    async def _handle_payment_cancelled(
        self,
        *,
        payment_row: Mapping[str, object],
        payload: Mapping[str, object],
    ) -> None:
        await self._db.execute(
            sa.text(
                """
                UPDATE payments
                SET status = 'cancelled',
                    provider_data_json = CAST(:provider_data_json AS jsonb)
                WHERE id = :payment_id
                """
            ),
            {
                "payment_id": _to_uuid(payment_row["id"]),
                "provider_data_json": json.dumps(payload, ensure_ascii=False),
            },
        )

        order_id = _to_uuid(payment_row["order_id"])
        try:
            await self._order_service.transition_order(
                order_id=order_id,
                target_status="cancelled_by_buyer",
            )
        except InvalidTransitionError:
            # Payment can be cancelled after order already moved to final status.
            pass
        await self._db.commit()

    @beartype
    async def _ensure_brand_action_tokens(
        self,
        *,
        order_id: UUID,
        sub_orders: Sequence[Mapping[str, object]] | None = None,
    ) -> dict[UUID, ActionTokens]:
        if sub_orders is None:
            sub_orders_result = await self._db.execute(
                sa.text(
                    """
                    SELECT id, brand_id
                    FROM sub_orders
                    WHERE order_id = :order_id
                    ORDER BY created_at ASC, id ASC
                    """
                ),
                {"order_id": order_id},
            )
            sub_orders = sub_orders_result.mappings().all()
        expires_at = datetime.now(UTC) + timedelta(hours=settings.order_action_token_ttl_hours)
        payload: dict[UUID, ActionTokens] = {}
        for row in sub_orders:
            sub_order_id = _to_uuid(row["id"])
            brand_id = _to_uuid(row["brand_id"])
            confirm_token = await self._ensure_single_action_token(
                order_id=order_id,
                sub_order_id=sub_order_id,
                brand_id=brand_id,
                action_type="confirm",
                expires_at=expires_at,
            )
            cancel_token = await self._ensure_single_action_token(
                order_id=order_id,
                sub_order_id=sub_order_id,
                brand_id=brand_id,
                action_type="cancel",
                expires_at=expires_at,
            )
            ship_token = await self._ensure_single_action_token(
                order_id=order_id,
                sub_order_id=sub_order_id,
                brand_id=brand_id,
                action_type="ship",
                expires_at=expires_at,
            )
            payload[brand_id] = ActionTokens(
                confirm=confirm_token,
                cancel=cancel_token,
                ship=ship_token,
            )
        return payload

    @beartype
    async def _ensure_single_action_token(
        self,
        *,
        order_id: UUID,
        sub_order_id: UUID,
        brand_id: UUID,
        action_type: str,
        expires_at: datetime,
    ) -> str:
        existing = await self._db.execute(
            sa.text(
                """
                SELECT token
                FROM order_action_tokens
                WHERE sub_order_id = :sub_order_id
                  AND brand_id = :brand_id
                  AND action_type = :action_type
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {
                "order_id": order_id,
                "sub_order_id": sub_order_id,
                "brand_id": brand_id,
                "action_type": action_type,
            },
        )
        existing_row = existing.mappings().first()
        if existing_row is not None:
            return str(existing_row["token"])

        token = str(uuid4())
        await self._db.execute(
            sa.text(
                """
                INSERT INTO order_action_tokens (
                    order_id,
                    sub_order_id,
                    brand_id,
                    action_type,
                    token,
                    expires_at
                )
                VALUES (
                    :order_id,
                    :sub_order_id,
                    :brand_id,
                    :action_type,
                    :token,
                    :expires_at
                )
                """
            ),
            {
                "order_id": order_id,
                "sub_order_id": sub_order_id,
                "brand_id": brand_id,
                "action_type": action_type,
                "token": token,
                "expires_at": expires_at,
            },
        )
        return token

    @beartype
    async def _create_receipt(
        self,
        *,
        payment_row: Mapping[str, object],
        object_payload: Mapping[str, object],
        order_id: UUID,
    ) -> str | None:
        external_payment_id = cast(str | None, payment_row["external_payment_id"])
        if not external_payment_id:
            return None

        email = await self._resolve_buyer_email(order_id=order_id)
        if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
            if settings.app_env.strip().lower() == "production":
                # Fail closed in production (CR-005): never store a fake receipt URL.
                # The payment flow tolerates a missing receipt_url, so log loudly and skip.
                logger.warning(
                    "YooKassa credentials are not configured in production; "
                    "skipping fiscal receipt for payment %s.",
                    external_payment_id,
                )
                return None
            # Mock URL is only for local/dev environments without real credentials.
            return f"https://mock.yookassa.local/receipts/{external_payment_id}"
        if not email:
            email = settings.unisender_sender_email

        order_items = await self._order_service.list_order_items(order_id=order_id)
        receipt_items: list[dict[str, object]] = []
        for item in order_items:
            quantity = _to_decimal(item["quantity"]).quantize(Decimal("0.01"))
            price = _to_decimal(item["unit_price"]).quantize(Decimal("0.01"))
            receipt_items.append(
                {
                    "description": str(item["product_name"]),
                    "quantity": str(quantity),
                    "amount": {"value": str(price), "currency": "RUB"},
                    "vat_code": 1,
                    "payment_mode": "full_prepayment",
                    "payment_subject": "commodity",
                }
            )

        payload = {
            "type": "payment",
            "payment_id": external_payment_id,
            "send": True,
            "customer": {"email": email},
            "items": receipt_items,
            "metadata": object_payload.get("metadata", {}),
        }
        try:
            async with httpx.AsyncClient(
                auth=(settings.yookassa_shop_id, settings.yookassa_secret_key),
                timeout=20.0,
            ) as client:
                response = await client.post(
                    "https://api.yookassa.ru/v3/receipts",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except Exception:
            return None

        receipt_id = str(data.get("id", "")).strip()
        if not receipt_id:
            return None
        return f"https://yookassa.ru/receipt/{receipt_id}"

    @beartype
    async def _resolve_buyer_email(self, *, order_id: UUID) -> str | None:
        result = await self._db.execute(
            sa.text(
                """
                SELECT u.email
                FROM orders o
                JOIN users u ON u.id = o.user_id
                WHERE o.id = :order_id
                LIMIT 1
                """
            ),
            {"order_id": order_id},
        )
        row = result.mappings().first()
        if row is None:
            return None
        value = row["email"]
        if value is None:
            return None
        return str(value)

    @beartype
    async def _get_payment_by_external_id(
        self,
        *,
        external_payment_id: str,
    ) -> Mapping[str, object] | None:
        result = await self._db.execute(
            sa.text(
                """
                SELECT id, order_id, external_payment_id, status, amount
                FROM payments
                WHERE external_payment_id = :external_payment_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"external_payment_id": external_payment_id},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return row

    @beartype
    def _verify_signature(self, *, raw_body: bytes, headers: Mapping[str, str]) -> None:
        normalized_headers = {key.lower(): value for key, value in headers.items()}
        webhook_secret = settings.yookassa_webhook_secret.strip()
        if webhook_secret:
            sent_signature = normalized_headers.get("x-yookassa-signature", "")
            expected_signature = hmac.new(
                webhook_secret.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            if not sent_signature or not secrets.compare_digest(sent_signature, expected_signature):
                raise InvalidWebhookSignatureError("Invalid webhook signature.")
            return

        auth_header = normalized_headers.get("authorization", "")
        shop_id = settings.yookassa_shop_id.strip()
        secret_key = settings.yookassa_secret_key.strip()
        if shop_id and secret_key:
            expected = base64.b64encode(f"{shop_id}:{secret_key}".encode()).decode("utf-8")
            expected_header = f"Basic {expected}"
            if not auth_header or not secrets.compare_digest(auth_header, expected_header):
                raise InvalidWebhookSignatureError("Invalid webhook authorization.")
            return

        raise InvalidWebhookSignatureError("YooKassa webhook credentials are not configured.")
