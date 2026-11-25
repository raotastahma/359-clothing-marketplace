from __future__ import annotations

# mypy: disable-error-code=import-untyped
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "threefivenine",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "yml-sync-all-due-feeds": {
            "task": "yml.sync_all_due_feeds",
            "schedule": crontab(minute="*/10"),
        },
        "delivery-refresh-tracking": {
            "task": "delivery.refresh_tracking_statuses",
            "schedule": crontab(minute=0, hour="*/2"),
            "kwargs": {"limit": 200},
        },
        "sla-check-deadlines": {
            "task": "sla.check_deadlines",
            "schedule": crontab(minute=0, hour="*"),
        },
    },
)
