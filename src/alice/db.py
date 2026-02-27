"""Database engine and session factory."""

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alice.config import settings

# In Celery worker processes each task calls asyncio.run() which creates a new
# event loop per thread/process.  Sharing an asyncpg connection pool across
# different event loops causes InterfaceError / "Future attached to a different
# loop".  NullPool avoids the global pool entirely: every async-with block
# opens and closes its own connection.
_pool_kwargs: dict = {}
if os.environ.get("ALICE_WORKER"):
    from sqlalchemy.pool import NullPool
    _pool_kwargs["poolclass"] = NullPool

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, **_pool_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Dependency for FastAPI to provide DB sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
