from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260304_0003"
down_revision: str | None = "20260223_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )
    op.create_index("idx_users_is_admin", "users", ["is_admin"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_users_is_admin", table_name="users")
    op.drop_column("users", "is_admin")
