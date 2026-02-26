"""initial schema

Revision ID: 7311687d15f6
Revises:
Create Date: 2026-02-26 14:46:04.721247

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7311687d15f6"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum types idempotently via exception handling (safe for reruns)
    op.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE pipelinestatus AS ENUM "
        "('fetched', 'gatekept', 'understood', 'scored', 'indexed', 'failed'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    ))
    op.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE sourcetype AS ENUM ('rss', 'arxiv'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    ))
    op.execute(sa.text(
        "DO $$ BEGIN "
        "CREATE TYPE feedbacktype AS ENUM "
        "('valuable_learned', 'save_for_later', 'not_valuable', 'already_known'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    ))

    # Use create_type=False so create_table doesn't try to recreate these types
    pipelinestatus = postgresql.ENUM(
        "fetched", "gatekept", "understood", "scored", "indexed", "failed",
        name="pipelinestatus", create_type=False,
    )
    sourcetype = postgresql.ENUM("rss", "arxiv", name="sourcetype", create_type=False)
    feedbacktype = postgresql.ENUM(
        "valuable_learned", "save_for_later", "not_valuable", "already_known",
        name="feedbacktype", create_type=False,
    )

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_chat_id"),
    )

    # Create sources table
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sourcetype, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetch_interval_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create content table
    op.create_table(
        "content",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("title", sa.String(1024), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("pipeline_status", pipelinestatus, nullable=False, server_default="fetched"),
        sa.Column("pipeline_error", sa.Text(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("key_points", sa.JSON(), nullable=True),
        sa.Column("domains", sa.JSON(), nullable=True),
        sa.Column("estimated_read_time", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_url"),
    )

    # Create feedback table
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", feedbacktype, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["content.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("feedback")
    op.drop_table("content")
    op.drop_table("sources")
    op.drop_table("users")

    # Drop enum types
    sa.Enum(name="feedbacktype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="sourcetype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="pipelinestatus").drop(op.get_bind(), checkfirst=True)
