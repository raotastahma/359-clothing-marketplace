from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260306_0005"
down_revision: str | None = "20260305_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        WITH payout_groups AS (
            SELECT
                p.order_id,
                p.brand_id,
                MAX(p.amount) AS fallback_items_total,
                MIN(p.created_at) AS created_at
            FROM payouts p
            LEFT JOIN sub_orders so
                ON so.order_id = p.order_id
               AND so.brand_id = p.brand_id
            WHERE p.sub_order_id IS NULL
              AND so.id IS NULL
            GROUP BY p.order_id, p.brand_id
        ),
        item_totals AS (
            SELECT
                oi.order_id,
                oi.brand_id,
                SUM(oi.unit_price * oi.quantity) AS items_total,
                SUM(oi.commission_amount) AS commission_total
            FROM order_items oi
            JOIN payout_groups pg
                ON pg.order_id = oi.order_id
               AND pg.brand_id = oi.brand_id
            GROUP BY oi.order_id, oi.brand_id
        )
        INSERT INTO sub_orders (
            order_id,
            brand_id,
            status,
            items_total,
            commission_total,
            actual_delivery_cost,
            created_at
        )
        SELECT
            pg.order_id,
            pg.brand_id,
            'completed'::order_status,
            COALESCE(it.items_total, pg.fallback_items_total, 0),
            COALESCE(it.commission_total, 0),
            0,
            pg.created_at
        FROM payout_groups pg
        LEFT JOIN item_totals it
            ON it.order_id = pg.order_id
           AND it.brand_id = pg.brand_id
        ON CONFLICT (order_id, brand_id) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE order_items oi
        SET sub_order_id = so.id
        FROM sub_orders so
        WHERE oi.sub_order_id IS NULL
          AND oi.order_id = so.order_id
          AND oi.brand_id = so.brand_id
        """
    )
    op.execute(
        """
        UPDATE payouts p
        SET sub_order_id = so.id
        FROM sub_orders so
        WHERE p.sub_order_id IS NULL
          AND p.order_id = so.order_id
          AND p.brand_id = so.brand_id
        """
    )
    op.alter_column(
        "payouts",
        "sub_order_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_index("idx_payouts_sub_order", "payouts", ["sub_order_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_payouts_sub_order", table_name="payouts")
    op.alter_column(
        "payouts",
        "sub_order_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
