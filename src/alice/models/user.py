"""User model."""

from sqlalchemy import JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User table for Telegram users."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
