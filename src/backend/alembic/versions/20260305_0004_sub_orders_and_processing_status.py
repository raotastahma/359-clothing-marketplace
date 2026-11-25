from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260305_0004"
down_revision: str | None = "20260304_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

order_status_v2_enum = postgresql.ENUM(
    "pending",
    "paid",
    "processing",
    "shipped",
    "delivered",
    "completed",
    "cancelled_by_buyer",
    "cancelled_by_brand",
    "returned",
    name="order_status_v2",
    create_type=False,
)

order_status_old_enum = postgresql.ENUM(
    "pending",
    "paid",
    "confirmed",
    "shipped",
    "delivered",
    "completed",
    "cancelled",
    "cancelled_by_buyer",
    "cancelled_by_brand",
    "returned",
    name="order_status_old",
    create_type=False,
)


def _upgrade_order_status_enum() -> None:
    bind = op.get_bind()
    order_status_v2_enum.create(bind, checkfirst=False)
    op.execute("ALTER TABLE orders ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE orders
        ALTER COLUMN status TYPE order_status_v2
        USING (
            CASE
                WHEN status::text = 'confirmed' THEN 'processing'
                WHEN status::text = 'cancelled' THEN 'cancelled_by_buyer'
                ELSE status::text
            END
        )::order_status_v2
        """
    )
    op.execute("ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'pending'::order_status_v2")


def _downgrade_order_status_enum() -> None:
    bind = op.get_bind()
    order_status_old_enum.create(bind, checkfirst=False)
    op.execute("ALTER TABLE orders ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE orders
        ALTER COLUMN status TYPE order_status_old
        USING (
            CASE
                WHEN status::text = 'processing' THEN 'confirmed'
                ELSE status::text
            END
        )::order_status_old
        """
    )
    op.execute("ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'pending'::order_status_old")
    op.execute("DROP TYPE order_status")
    op.execute("ALTER TYPE order_status_old RENAME TO order_status")


def upgrade() -> None:
    _upgrade_order_status_enum()

    op.alter_column(
        "orders",
        "delivery_cost",
        new_column_name="customer_delivery_cost",
        existing_type=sa.Numeric(10, 2),
        existing_nullable=False,
        existing_server_default=sa.text("0"),
    )

    sub_orders_columns: list[Any] = [
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
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            order_status_v2_enum,
            nullable=False,
            server_default=sa.text("'paid'::order_status_v2"),
        ),
        sa.Column("items_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("commission_total", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "actual_delivery_cost",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("tracking_number", sa.String(length=100), nullable=True),
        sa.Column("confirmation_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipping_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("order_id", "brand_id", name="uq_sub_orders_order_brand"),
    ]

    op.create_table(
        "sub_orders",
        *sub_orders_columns,
    )
    op.create_index("idx_sub_orders_order", "sub_orders", ["order_id"], unique=False)
    op.create_index("idx_sub_orders_brand", "sub_orders", ["brand_id", "status"], unique=False)
    op.create_index(
        "idx_sub_orders_sla",
        "sub_orders",
        ["status", "confirmation_deadline"],
        unique=False,
        postgresql_where=sa.text("status = 'paid'::order_status_v2"),
    )

    op.add_column(
        "order_items",
        sa.Column("sub_order_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_order_items_sub_order_id_sub_orders",
        "order_items",
        "sub_orders",
        ["sub_order_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_order_items_sub_order", "order_items", ["sub_order_id"], unique=False)

    op.add_column(
        "order_action_tokens",
        sa.Column("sub_order_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_order_action_tokens_sub_order_id_sub_orders",
        "order_action_tokens",
        "sub_orders",
        ["sub_order_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_action_tokens_sub_order",
        "order_action_tokens",
        ["sub_order_id", "brand_id"],
        unique=False,
    )

    op.add_column(
        "payouts", sa.Column("sub_order_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_payouts_sub_order_id_sub_orders",
        "payouts",
        "sub_orders",
        ["sub_order_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "refunds", sa.Column("sub_order_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_refunds_sub_order_id_sub_orders",
        "refunds",
        "sub_orders",
        ["sub_order_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("idx_refunds_sub_order", "refunds", ["sub_order_id"], unique=False)

    op.execute("DROP TYPE order_status")
    op.execute("ALTER TYPE order_status_v2 RENAME TO order_status")


def downgrade() -> None:
    op.drop_index("idx_refunds_sub_order", table_name="refunds")
    op.drop_constraint("fk_refunds_sub_order_id_sub_orders", "refunds", type_="foreignkey")
    op.drop_column("refunds", "sub_order_id")

    op.drop_constraint("fk_payouts_sub_order_id_sub_orders", "payouts", type_="foreignkey")
    op.drop_column("payouts", "sub_order_id")

    op.drop_index("idx_action_tokens_sub_order", table_name="order_action_tokens")
    op.drop_constraint(
        "fk_order_action_tokens_sub_order_id_sub_orders",
        "order_action_tokens",
        type_="foreignkey",
    )
    op.drop_column("order_action_tokens", "sub_order_id")

    op.drop_index("idx_order_items_sub_order", table_name="order_items")
    op.drop_constraint(
        "fk_order_items_sub_order_id_sub_orders",
        "order_items",
        type_="foreignkey",
    )
    op.drop_column("order_items", "sub_order_id")

    op.drop_index("idx_sub_orders_sla", table_name="sub_orders")
    op.drop_index("idx_sub_orders_brand", table_name="sub_orders")
    op.drop_index("idx_sub_orders_order", table_name="sub_orders")
    op.drop_table("sub_orders")

    op.alter_column(
        "orders",
        "customer_delivery_cost",
        new_column_name="delivery_cost",
        existing_type=sa.Numeric(10, 2),
        existing_nullable=False,
        existing_server_default=sa.text("0"),
    )

    _downgrade_order_status_enum()
