from __future__ import annotations

# mypy: disable-error-code=attr-defined
# pyright: reportFunctionMemberAccess=false
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from beartype import beartype

from app.core.config import settings
from app.tasks.email_tasks import (
    send_brand_new_order_email_task,
    send_buyer_status_email_task,
    send_transactional_email_task,
)

__all__ = [
    "ActionTokens",
    "NotificationService",
    "send_brand_new_order_email_task",
    "send_buyer_status_email_task",
    "send_transactional_email_task",
]


@dataclass(frozen=True, slots=True)
class ActionTokens:
    confirm: str
    cancel: str
    ship: str


class NotificationService:
    @beartype
    def __init__(self, *, api_base_url: str | None = None) -> None:
        self._api_base_url = (api_base_url or settings.api_base_url).rstrip("/")

    @beartype
    def group_items_by_brand(
        self, items: Sequence[Mapping[str, object]]
    ) -> dict[UUID, list[dict[str, object]]]:
        grouped: dict[UUID, list[dict[str, object]]] = defaultdict(list)
        for item in items:
            brand_id_raw = item.get("brand_id")
            if brand_id_raw is None:
                continue
            brand_id = UUID(str(brand_id_raw))
            grouped[brand_id].append(dict(item))
        return dict(grouped)

    @beartype
    def build_action_links(self, *, token: ActionTokens) -> dict[str, str]:
        return {
            "confirm": f"{self._api_base_url}/orders/actions/{token.confirm}/confirm",
            "cancel": f"{self._api_base_url}/orders/actions/{token.cancel}/cancel",
            "ship": f"{self._api_base_url}/orders/actions/{token.ship}/ship",
        }

    @beartype
    async def notify_order_paid(
        self,
        *,
        order: Mapping[str, object],
        items: Sequence[Mapping[str, object]],
        brand_notification_emails: Mapping[UUID, list[str]],
        action_tokens: Mapping[UUID, ActionTokens],
    ) -> None:
        grouped = self.group_items_by_brand(items)
        order_number = str(order.get("number", order.get("id", "")))
        created_at = order.get("created_at")
        if isinstance(created_at, datetime):
            order_dt = created_at.isoformat()
        else:
            order_dt = str(created_at or "")

        customer_payload = {
            "full_name": str(order.get("buyer_full_name", "")),
            "phone": str(order.get("buyer_phone", "")),
            "address": str(order.get("delivery_address", "")),
        }

        for brand_id, brand_items in grouped.items():
            token = action_tokens.get(brand_id)
            if token is None:
                continue
            links = self.build_action_links(token=token)
            recipients = brand_notification_emails.get(brand_id, [])
            for email in recipients:
                send_brand_new_order_email_task.delay(
                    to=email,
                    order_number=order_number,
                    order_datetime=order_dt,
                    items=[dict(item) for item in brand_items],
                    customer=customer_payload,
                    actions=links,
                )

        buyer_email_value = order.get("buyer_email")
        if isinstance(buyer_email_value, str) and buyer_email_value:
            send_buyer_status_email_task.delay(
                to=buyer_email_value,
                template_id="buyer_order_confirmed",
                context={
                    "order_number": order_number,
                    "status": "paid",
                    "details": "Оплата получена, заказ передан бренду.",
                },
            )

    @beartype
    async def notify_buyer_status_update(
        self,
        *,
        email: str,
        order_number: str,
        status: str,
        details: str,
        tracking_number: str | None = None,
    ) -> None:
        template_id = self._template_for_status(status=status)
        context: dict[str, object] = {
            "order_number": order_number,
            "status": status,
            "details": details,
        }
        if tracking_number is not None:
            context["tracking_number"] = tracking_number

        send_buyer_status_email_task.delay(
            to=email,
            template_id=template_id,
            context=context,
        )

    @beartype
    async def send_sla_alert(
        self,
        *,
        to: str,
        sub_order: Mapping[str, object],
        alert_type: str,
    ) -> None:
        if not to.strip():
            return
        send_transactional_email_task.delay(
            to=to,
            template_id="sla_alert_to_head_of_partnerships",
            context={
                "alert_type": alert_type,
                "sub_order_id": str(sub_order["id"]),
                "order_id": str(sub_order["order_id"]),
                "brand_id": str(sub_order["brand_id"]),
                "brand_name": str(sub_order.get("brand_name", "")),
                "status": str(sub_order["status"]),
                "confirmation_deadline": str(sub_order.get("confirmation_deadline") or ""),
                "shipping_deadline": str(sub_order.get("shipping_deadline") or ""),
            },
        )

    @beartype
    def _template_for_status(self, *, status: str) -> str:
        if status == "processing":
            return "buyer_order_confirmed"
        if status == "shipped":
            return "buyer_order_shipped"
        if status in {"delivered", "completed"}:
            return "buyer_order_delivered"
        if status in {"cancelled_by_brand", "cancelled_by_buyer", "cancelled"}:
            return "buyer_order_cancelled"
        return "buyer_status_update"
