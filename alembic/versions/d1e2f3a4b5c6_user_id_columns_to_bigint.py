"""user id columns to bigint

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4g5h6
Create Date: 2026-02-28 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "c1d2e3f4g5h6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen users.id and all user_id FK columns from INTEGER to BIGINT.

    Telegram user IDs can exceed the int32 range (max 2,147,483,647),
    so all columns storing or referencing them must be BIGINT.
    """
    # users.id  (PK)
    op.alter_column("users", "id", type_=sa.BigInteger(), existing_type=sa.Integer())

    # Foreign-key columns referencing users.id
    op.alter_column("content", "user_id", type_=sa.BigInteger(), existing_type=sa.Integer())
    op.alter_column("feedback", "user_id", type_=sa.BigInteger(), existing_type=sa.Integer())
    op.alter_column("review_cards", "user_id", type_=sa.BigInteger(), existing_type=sa.Integer())
    op.alter_column("user_memories", "user_id", type_=sa.BigInteger(), existing_type=sa.Integer())


def downgrade() -> None:
    """Revert BIGINT back to INTEGER."""
    op.alter_column("user_memories", "user_id", type_=sa.Integer(), existing_type=sa.BigInteger())
    op.alter_column("review_cards", "user_id", type_=sa.Integer(), existing_type=sa.BigInteger())
    op.alter_column("feedback", "user_id", type_=sa.Integer(), existing_type=sa.BigInteger())
    op.alter_column("content", "user_id", type_=sa.Integer(), existing_type=sa.BigInteger())
    op.alter_column("users", "id", type_=sa.Integer(), existing_type=sa.BigInteger())
