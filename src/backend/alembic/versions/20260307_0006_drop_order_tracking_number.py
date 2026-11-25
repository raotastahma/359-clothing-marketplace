from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260307_0006"
down_revision: str | None = "20260306_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("orders", "tracking_number")


def downgrade() -> None:
    op.add_column("orders", sa.Column("tracking_number", sa.String(length=100), nullable=True))
