from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin.brands import router as admin_brands_router
from app.api.v1.admin.finance import router as admin_finance_router
from app.api.v1.admin.products import router as admin_products_router
from app.api.v1.admin.sync import router as admin_sync_router
from app.api.v1.auth import router as auth_router
from app.api.v1.brand_portal.analytics import router as brand_portal_analytics_router
from app.api.v1.brand_portal.auth import router as brand_portal_auth_router
from app.api.v1.brand_portal.finance import router as brand_portal_finance_router
from app.api.v1.brand_portal.orders import router as brand_portal_orders_router
from app.api.v1.brand_portal.products import router as brand_portal_products_router
from app.api.v1.brands import router as brands_router
from app.api.v1.cart import router as cart_router
from app.api.v1.categories import router as categories_router
from app.api.v1.delivery import router as delivery_router
from app.api.v1.order_actions import router as order_actions_router
from app.api.v1.orders import router as orders_router
from app.api.v1.payments import router as payments_router
from app.api.v1.products import router as products_router
from app.api.v1.users import router as users_router
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.redis import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await redis_client.aclose()


app = FastAPI(
    title="359 Marketplace API",
    version="0.1.0",
    lifespan=lifespan,
)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(brand_portal_auth_router, prefix="/api/v1")
app.include_router(brand_portal_analytics_router, prefix="/api/v1")
app.include_router(brand_portal_finance_router, prefix="/api/v1")
app.include_router(brand_portal_orders_router, prefix="/api/v1")
app.include_router(brand_portal_products_router, prefix="/api/v1")
app.include_router(admin_brands_router, prefix="/api/v1")
app.include_router(admin_finance_router, prefix="/api/v1")
app.include_router(admin_products_router, prefix="/api/v1")
app.include_router(admin_sync_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(brands_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(delivery_router, prefix="/api/v1")
app.include_router(cart_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(order_actions_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
