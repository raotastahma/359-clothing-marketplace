from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.order import (
    OrderDetailPayload,
    OrderDetailResponse,
    OrderListResponse,
    OrderStatusPayload,
    OrderSummaryPayload,
    PaginationMeta,
    SubOrderSummary,
)


def _sub_order_payload() -> SubOrderSummary:
    return SubOrderSummary(
        id=uuid4(),
        brand_name="MASLOV",
        status="processing",
        tracking_number=None,
        items_count=1,
    )


def test_order_list_response_accepts_processing_and_sub_orders() -> None:
    response = OrderListResponse(
        data=[
            OrderSummaryPayload(
                id=uuid4(),
                status="processing",
                total_amount=Decimal("1200.00"),
                customer_delivery_cost=Decimal("0.00"),
                items_count=1,
                sub_orders=[_sub_order_payload()],
                paid_at=None,
                shipped_at=None,
                delivered_at=None,
                created_at=datetime.now(UTC),
            )
        ],
        meta=PaginationMeta(page=1, per_page=10, total=1),
    )

    assert response.data[0].status == "processing"
    assert response.data[0].sub_orders[0].brand_name == "MASLOV"
    assert response.data[0].sub_orders[0].items_count == 1
    assert response.data[0].sub_orders[0].status == "processing"


def test_sub_order_summary_rejects_internal_fields() -> None:
    with pytest.raises(ValidationError):
        SubOrderSummary.model_validate(
            {
                "id": uuid4(),
                "brand_name": "MASLOV",
                "status": "processing",
                "tracking_number": None,
                "items_count": 1,
                "brand_id": uuid4(),
            }
        )


def test_order_detail_response_rejects_legacy_confirmed_status() -> None:
    with pytest.raises(ValidationError):
        OrderDetailResponse.model_validate(
            {
                "data": {
                    "id": uuid4(),
                    "status": "confirmed",
                    "total_amount": Decimal("1200.00"),
                    "commission_total": Decimal("420.00"),
                    "customer_delivery_cost": Decimal("0.00"),
                    "delivery_provider": "yandex_delivery",
                    "delivery_method": "courier",
                    "delivery_address": {"city": "Moscow"},
                    "items": [],
                    "sub_orders": [_sub_order_payload().model_dump()],
                    "paid_at": None,
                    "shipped_at": None,
                    "delivered_at": None,
                    "created_at": datetime.now(UTC),
                }
            }
        )


def test_customer_order_payloads_do_not_define_order_level_tracking() -> None:
    assert "tracking_number" not in OrderSummaryPayload.model_fields
    assert "tracking_number" not in OrderDetailPayload.model_fields
    assert "tracking_number" not in OrderStatusPayload.model_fields
