from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.brand import BrandCreateRequest


def test_brand_create_validates_notification_emails() -> None:
    payload = BrandCreateRequest(
        name="MASLOV",
        notification_emails=["orders@maslov.ru"],
        commission_rate=Decimal("0.35"),
    )
    assert payload.notification_emails == ["orders@maslov.ru"]


def test_brand_create_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        BrandCreateRequest(
            name="MASLOV",
            notification_emails=["invalid-email"],
            commission_rate=Decimal("0.35"),
        )
