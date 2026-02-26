"""add_p_score_to_content

Revision ID: a1b2c3d4e5f6
Revises: 01a7e7d9a52f
Create Date: 2026-02-26 15:52:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "01a7e7d9a52f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add p_score column to content table."""
    op.add_column(
        "content",
        sa.Column("p_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Remove p_score column from content table."""
    op.drop_column("content", "p_score")
