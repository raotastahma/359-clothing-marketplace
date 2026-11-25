from __future__ import annotations

# mypy: disable-error-code=untyped-decorator
# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
import asyncio

from app.integrations.email import get_email_provider
from app.tasks.celery_app import celery_app


def _run(awaitable: object) -> str:
    return str(asyncio.run(awaitable))  # type: ignore[arg-type]


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    name="email.send_transactional",
)
def send_transactional_email_task(
    self: object,
    *,
    to: str,
    template_id: str,
    context: dict[str, object],
) -> str:
    _ = self
    provider = get_email_provider()
    return _run(provider.send_transactional_email(to=to, template_id=template_id, context=context))


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    name="email.send_brand_new_order",
)
def send_brand_new_order_email_task(
    self: object,
    *,
    to: str,
    order_number: str,
    order_datetime: str,
    items: list[dict[str, object]],
    customer: dict[str, object],
    actions: dict[str, str],
) -> str:
    _ = self
    provider = get_email_provider()
    return _run(
        provider.send_transactional_email(
            to=to,
            template_id="brand_new_order",
            context={
                "order_number": order_number,
                "order_datetime": order_datetime,
                "items": items,
                "customer": customer,
                "actions": actions,
            },
        )
    )


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    name="email.send_buyer_status",
)
def send_buyer_status_email_task(
    self: object,
    *,
    to: str,
    template_id: str,
    context: dict[str, object],
) -> str:
    _ = self
    provider = get_email_provider()
    return _run(
        provider.send_transactional_email(
            to=to,
            template_id=template_id,
            context=context,
        )
    )
