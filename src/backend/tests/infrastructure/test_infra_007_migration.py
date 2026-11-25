from __future__ import annotations

from pathlib import Path

MIGRATION_SOURCE = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "20260305_0004_sub_orders_and_processing_status.py"
).read_text()


def test_order_status_migration_uses_type_swap_for_processing() -> None:
    assert "ALTER TYPE order_status ADD VALUE" not in MIGRATION_SOURCE
    assert "order_status_v2" in MIGRATION_SOURCE
    assert "WHEN status::text = 'confirmed' THEN 'processing'" in MIGRATION_SOURCE


def test_order_status_migration_resets_default_around_type_cast() -> None:
    drop_default = "ALTER TABLE orders ALTER COLUMN status DROP DEFAULT"
    set_v2_default = "ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'pending'::order_status_v2"
    set_old_default = (
        "ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'pending'::order_status_old"
    )

    assert MIGRATION_SOURCE.index(drop_default) < MIGRATION_SOURCE.index(
        "ALTER COLUMN status TYPE order_status_v2"
    )
    assert MIGRATION_SOURCE.index("ALTER COLUMN status TYPE order_status_v2") < (
        MIGRATION_SOURCE.index(set_v2_default)
    )
    assert set_old_default in MIGRATION_SOURCE
