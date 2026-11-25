from __future__ import annotations

# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260223_0002"
down_revision: str | None = "20260218_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

product_status_enum = postgresql.ENUM(
    "active",
    "hidden",
    "archived",
    name="product_status",
    create_type=False,
)
feed_sync_status_enum = postgresql.ENUM(
    "running",
    "success",
    "error",
    name="feed_sync_status",
    create_type=False,
)
order_action_type_enum = postgresql.ENUM(
    "confirm",
    "cancel",
    "ship",
    name="order_action_type",
    create_type=False,
)


def _create_new_enums() -> None:
    bind = op.get_bind()
    product_status_enum.create(bind, checkfirst=True)
    feed_sync_status_enum.create(bind, checkfirst=True)
    order_action_type_enum.create(bind, checkfirst=True)


def _drop_new_enums() -> None:
    bind = op.get_bind()
    order_action_type_enum.drop(bind, checkfirst=True)
    feed_sync_status_enum.drop(bind, checkfirst=True)
    product_status_enum.drop(bind, checkfirst=True)


def _extend_order_status_enum() -> None:
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'confirmed'")
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'cancelled_by_brand'")
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'cancelled_by_buyer'")
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'completed'")


def _downgrade_order_status_enum() -> None:
    op.execute(
        """
        CREATE TYPE order_status_old AS ENUM (
            'pending',
            'paid',
            'shipped',
            'delivered',
            'cancelled',
            'returned'
        )
        """
    )
    op.execute(
        """
        ALTER TABLE orders
        ALTER COLUMN status TYPE order_status_old
        USING (
            CASE
                WHEN status::text = 'confirmed' THEN 'paid'
                WHEN status::text = 'completed' THEN 'delivered'
                WHEN status::text IN ('cancelled_by_brand', 'cancelled_by_buyer') THEN 'cancelled'
                ELSE status::text
            END
        )::order_status_old
        """
    )
    op.execute("DROP TYPE order_status")
    op.execute("ALTER TYPE order_status_old RENAME TO order_status")


def upgrade() -> None:
    _create_new_enums()
    _extend_order_status_enum()

    op.add_column(
        "brands",
        sa.Column(
            "notification_emails",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("brands", sa.Column("yml_feed_url", sa.String(length=512), nullable=True))
    op.add_column(
        "brands",
        sa.Column(
            "yml_sync_schedule",
            sa.String(length=50),
            nullable=True,
            server_default=sa.text("'0 */4 * * *'"),
        ),
    )
    op.add_column(
        "brands",
        sa.Column("payout_bank_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.add_column("products", sa.Column("fabric_composition", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("care_instructions", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("season", sa.String(length=50), nullable=True))
    op.add_column("products", sa.Column("base_price_rub", sa.Numeric(10, 2), nullable=True))
    op.add_column("products", sa.Column("sale_price_rub", sa.Numeric(10, 2), nullable=True))
    op.add_column(
        "products",
        sa.Column(
            "product_status",
            product_status_enum,
            nullable=False,
            server_default=sa.text("'active'::product_status"),
        ),
    )

    op.add_column(
        "product_variants", sa.Column("vendor_code", sa.String(length=100), nullable=True)
    )
    op.create_index(
        "idx_variants_vendor_code",
        "product_variants",
        ["vendor_code"],
        unique=True,
        postgresql_where=sa.text("vendor_code IS NOT NULL"),
    )

    op.create_table(
        "feed_sync_logs",
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
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            feed_sync_status_enum,
            nullable=False,
            server_default=sa.text("'running'::feed_sync_status"),
        ),
        sa.Column(
            "updated_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "unmatched_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_feed_sync_brand",
        "feed_sync_logs",
        ["brand_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "order_action_tokens",
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
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", order_action_type_enum, nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_action_tokens_token",
        "order_action_tokens",
        ["token"],
        unique=True,
    )
    op.create_index(
        "idx_action_tokens_order",
        "order_action_tokens",
        ["order_id", "brand_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_action_tokens_order", table_name="order_action_tokens")
    op.drop_index("idx_action_tokens_token", table_name="order_action_tokens")
    op.drop_table("order_action_tokens")

    op.drop_index("idx_feed_sync_brand", table_name="feed_sync_logs")
    op.drop_table("feed_sync_logs")

    op.drop_index("idx_variants_vendor_code", table_name="product_variants")
    op.drop_column("product_variants", "vendor_code")

    op.drop_column("products", "product_status")
    op.drop_column("products", "sale_price_rub")
    op.drop_column("products", "base_price_rub")
    op.drop_column("products", "season")
    op.drop_column("products", "care_instructions")
    op.drop_column("products", "fabric_composition")

    op.drop_column("brands", "payout_bank_details")
    op.drop_column("brands", "yml_sync_schedule")
    op.drop_column("brands", "yml_feed_url")
    op.drop_column("brands", "notification_emails")

    _downgrade_order_status_enum()
    _drop_new_enums()
