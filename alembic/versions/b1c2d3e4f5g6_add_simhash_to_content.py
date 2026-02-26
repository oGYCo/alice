"""add_simhash_to_content

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f6
Create Date: 2026-02-26 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5g6"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add simhash column to content table."""
    op.add_column(
        "content",
        sa.Column("simhash", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove simhash column from content table."""
    op.drop_column("content", "simhash")
