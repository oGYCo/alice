"""add_pushed_at_to_content

Revision ID: 01a7e7d9a52f
Revises: 7311687d15f6
Create Date: 2026-02-26 15:51:32.522003

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "01a7e7d9a52f"
down_revision: str | Sequence[str] | None = "7311687d15f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add pushed_at column to content table."""
    op.add_column(
        "content",
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove pushed_at column from content table."""
    op.drop_column("content", "pushed_at")
