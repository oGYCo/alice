"""add review_cards and user_memories tables

Revision ID: c1d2e3f4g5h6
Revises: b1c2d3e4f5g6
Create Date: 2026-02-26 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1d2e3f4g5h6"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5g6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_cards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("concept_id", sa.String(255), nullable=False),
        sa.Column("review_prompt", sa.Text(), nullable=False),
        sa.Column("stability", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("difficulty", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="new"),
        sa.Column("reps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lapses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "user_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("layer", sa.String(20), nullable=False),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("last_touched", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("user_memories")
    op.drop_table("review_cards")
