from __future__ import annotations

# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260218_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

brand_role_enum = postgresql.ENUM(
    "owner",
    "manager",
    "viewer",
    name="brand_role",
    create_type=False,
)
gender_type_enum = postgresql.ENUM(
    "men",
    "women",
    "unisex",
    name="gender_type",
    create_type=False,
)
order_status_enum = postgresql.ENUM(
    "pending",
    "paid",
    "shipped",
    "delivered",
    "cancelled",
    "returned",
    name="order_status",
    create_type=False,
)
delivery_provider_type_enum = postgresql.ENUM(
    "yandex_delivery",
    name="delivery_provider_type",
    create_type=False,
)
payment_provider_type_enum = postgresql.ENUM(
    "yookassa",
    name="payment_provider_type",
    create_type=False,
)
payment_status_enum = postgresql.ENUM(
    "pending",
    "waiting_for_capture",
    "succeeded",
    "cancelled",
    "refunded",
    name="payment_status",
    create_type=False,
)
payout_status_enum = postgresql.ENUM(
    "pending",
    "scheduled",
    "processing",
    "completed",
    "failed",
    name="payout_status",
    create_type=False,
)
refund_status_enum = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "rejected",
    name="refund_status",
    create_type=False,
)
notification_type_enum = postgresql.ENUM(
    "order_status",
    "delivery",
    "promotion",
    "payout",
    "system",
    name="notification_type",
    create_type=False,
)

ALL_ENUMS: tuple[postgresql.ENUM, ...] = (
    brand_role_enum,
    gender_type_enum,
    order_status_enum,
    delivery_provider_type_enum,
    payment_provider_type_enum,
    payment_status_enum,
    payout_status_enum,
    refund_status_enum,
    notification_type_enum,
)


def _create_enums() -> None:
    bind = op.get_bind()
    for enum_type in ALL_ENUMS:
        enum_type.create(bind, checkfirst=True)


def _drop_enums() -> None:
    bind = op.get_bind()
    for enum_type in reversed(ALL_ENUMS):
        enum_type.drop(bind, checkfirst=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    _create_enums()

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
    )
    op.create_index("idx_users_phone", "users", ["phone"], unique=False)
    op.create_index(
        "idx_users_email",
        "users",
        ["email"],
        unique=False,
        postgresql_where=sa.text("email IS NOT NULL"),
    )

    op.create_table(
        "brands",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("cover_url", sa.String(length=512), nullable=True),
        sa.Column(
            "commission_rate",
            sa.Numeric(5, 4),
            nullable=False,
            server_default=sa.text("0.3500"),
        ),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("slug", name="uq_brands_slug"),
    )
    op.create_index("idx_brands_slug", "brands", ["slug"], unique=True)

    op.create_table(
        "brand_users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            brand_role_enum,
            nullable=False,
            server_default=sa.text("'viewer'::brand_role"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("brand_id", "user_id", name="uq_brand_users_brand_user"),
    )
    op.create_index("idx_brand_users_user", "brand_users", ["user_id"], unique=False)
    op.create_index("idx_brand_users_brand", "brand_users", ["brand_id"], unique=False)

    op.create_table(
        "categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column(
            "gender",
            gender_type_enum,
            nullable=False,
            server_default=sa.text("'unisex'::gender_type"),
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )
    op.create_index("idx_categories_slug", "categories", ["slug"], unique=True)
    op.create_index("idx_categories_parent", "categories", ["parent_id"], unique=False)

    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "is_new_arrival",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("slug", name="uq_products_slug"),
    )
    op.create_index("idx_products_slug", "products", ["slug"], unique=True)
    op.create_index(
        "idx_products_catalog",
        "products",
        ["brand_id", "is_active", "category_id"],
        unique=False,
    )
    op.create_index(
        "idx_products_brand_active",
        "products",
        ["brand_id", "is_active"],
        unique=False,
    )
    op.execute(
        "CREATE INDEX idx_products_search ON products USING GIN "
        "(to_tsvector('russian', name || ' ' || COALESCE(description, '')))"
    )

    op.create_table(
        "product_variants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("size", sa.String(length=20), nullable=False),
        sa.Column("color", sa.String(length=50), nullable=True),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("price_rub", sa.Numeric(10, 2), nullable=False),
        sa.Column("compare_at_price_rub", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "stock_quantity",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.CheckConstraint("price_rub > 0", name="positive_price"),
        sa.CheckConstraint("stock_quantity >= 0", name="non_negative_stock"),
        sa.UniqueConstraint("sku", name="uq_product_variants_sku"),
    )
    op.create_index("idx_variants_product", "product_variants", ["product_id"], unique=False)
    op.create_index("idx_variants_sku", "product_variants", ["sku"], unique=True)

    op.create_table(
        "product_images",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "idx_images_product",
        "product_images",
        ["product_id", "sort_order"],
        unique=False,
    )

    op.create_table(
        "orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            order_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::order_status"),
        ),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("delivery_provider", delivery_provider_type_enum, nullable=True),
        sa.Column("delivery_method", sa.String(length=100), nullable=True),
        sa.Column(
            "delivery_cost",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("delivery_address_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tracking_number", sa.String(length=100), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute("CREATE INDEX idx_orders_user ON orders(user_id, created_at DESC)")
    op.create_index("idx_orders_status", "orders", ["status"], unique=False)

    op.create_table(
        "order_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("commission_rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("commission_amount", sa.Numeric(10, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="positive_quantity"),
    )
    op.create_index("idx_order_items_order", "order_items", ["order_id"], unique=False)
    op.create_index(
        "idx_order_items_brand",
        "order_items",
        ["order_id", "brand_id"],
        unique=False,
    )

    op.create_table(
        "payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", payment_provider_type_enum, nullable=False),
        sa.Column("external_payment_id", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            payment_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::payment_status"),
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("receipt_url", sa.String(length=512), nullable=True),
        sa.Column("provider_data_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_payments_order", "payments", ["order_id"], unique=False)
    op.create_index(
        "idx_payments_external",
        "payments",
        ["provider", "external_payment_id"],
        unique=False,
    )

    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(length=100), primary_key=True, nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "payouts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "status",
            payout_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::payout_status"),
        ),
        sa.Column("payout_delay_days", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_payouts_brand", "payouts", ["brand_id", "status"], unique=False)
    op.create_index(
        "idx_payouts_schedule",
        "payouts",
        ["status", "scheduled_at"],
        unique=False,
        postgresql_where=sa.text("status IN ('pending', 'scheduled')"),
    )

    op.create_table(
        "refunds",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "order_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("order_items.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("commission_refund", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            refund_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::refund_status"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_refunds_order", "refunds", ["order_id"], unique=False)

    op.create_table(
        "addresses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("street", sa.String(length=500), nullable=False),
        sa.Column("apartment", sa.String(length=50), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_addresses_user", "addresses", ["user_id"], unique=False)

    op.create_table(
        "favorites",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "product_id", name="uq_favorites_user_product"),
    )
    op.execute("CREATE INDEX idx_favorites_user ON favorites(user_id, created_at DESC)")

    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", notification_type_enum, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        "CREATE INDEX idx_notifications_user ON notifications(user_id, is_read, created_at DESC)"
    )

    op.create_table(
        "cart_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "product_variant_id", name="uq_cart_items_user_variant"),
        sa.CheckConstraint("quantity > 0", name="positive_cart_quantity"),
    )
    op.create_index("idx_cart_user", "cart_items", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_cart_user", table_name="cart_items")
    op.drop_table("cart_items")

    op.drop_index("idx_notifications_user", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("idx_favorites_user", table_name="favorites")
    op.drop_table("favorites")

    op.drop_index("idx_addresses_user", table_name="addresses")
    op.drop_table("addresses")

    op.drop_index("idx_refunds_order", table_name="refunds")
    op.drop_table("refunds")

    op.drop_index("idx_payouts_schedule", table_name="payouts")
    op.drop_index("idx_payouts_brand", table_name="payouts")
    op.drop_table("payouts")

    op.drop_table("platform_settings")

    op.drop_index("idx_payments_external", table_name="payments")
    op.drop_index("idx_payments_order", table_name="payments")
    op.drop_table("payments")

    op.drop_index("idx_order_items_brand", table_name="order_items")
    op.drop_index("idx_order_items_order", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("idx_orders_status", table_name="orders")
    op.drop_index("idx_orders_user", table_name="orders")
    op.drop_table("orders")

    op.drop_index("idx_images_product", table_name="product_images")
    op.drop_table("product_images")

    op.drop_index("idx_variants_sku", table_name="product_variants")
    op.drop_index("idx_variants_product", table_name="product_variants")
    op.drop_table("product_variants")

    op.drop_index("idx_products_search", table_name="products")
    op.drop_index("idx_products_brand_active", table_name="products")
    op.drop_index("idx_products_catalog", table_name="products")
    op.drop_index("idx_products_slug", table_name="products")
    op.drop_table("products")

    op.drop_index("idx_categories_parent", table_name="categories")
    op.drop_index("idx_categories_slug", table_name="categories")
    op.drop_table("categories")

    op.drop_index("idx_brand_users_brand", table_name="brand_users")
    op.drop_index("idx_brand_users_user", table_name="brand_users")
    op.drop_table("brand_users")

    op.drop_index("idx_brands_slug", table_name="brands")
    op.drop_table("brands")

    op.drop_index("idx_users_email", table_name="users")
    op.drop_index("idx_users_phone", table_name="users")
    op.drop_table("users")

    _drop_enums()
