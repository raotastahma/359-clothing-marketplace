from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.deps import require_scope
from app.integrations.delivery import get_delivery_provider
from app.schemas.delivery import DeliveryCalculateResponse, DeliveryCalculateResponseData

router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.get(
    "/calculate",
    response_model=DeliveryCalculateResponse,
    dependencies=[Depends(require_scope("customer", "admin"))],
)
async def calculate_delivery_cost(
    city: str = Query(min_length=1),
    street: str | None = Query(default=None),
    postal_code: str | None = Query(default=None),
    weight_kg: float = Query(default=1.0, gt=0),
    length_cm: float = Query(default=30.0, gt=0),
    width_cm: float = Query(default=20.0, gt=0),
    height_cm: float = Query(default=10.0, gt=0),
) -> DeliveryCalculateResponse:
    provider = get_delivery_provider()
    estimate = await provider.calculate_cost(
        address={
            "city": city,
            "street": street or "",
            "postal_code": postal_code or "",
        },
        weight_kg=weight_kg,
        dimensions={
            "length_cm": length_cm,
            "width_cm": width_cm,
            "height_cm": height_cm,
        },
    )
    return DeliveryCalculateResponse(
        data=DeliveryCalculateResponseData(
            cost=estimate.cost,
            estimated_days=estimate.estimated_days,
        )
    )
