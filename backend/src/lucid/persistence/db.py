"""Database engine, session factory, and readiness probe."""

import logging
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str) -> None:
    """Create the engine and session factory. Call once per process."""
    global _engine, _session_factory

    _engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        future=True,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


def get_engine() -> AsyncEngine:
    """Return the initialized engine."""
    if _engine is None:
        raise RuntimeError("Database engine is not initialized")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the initialized session factory."""
    if _session_factory is None:
        raise RuntimeError("Database session factory is not initialized")
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a session per request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def check_database() -> bool:
    """Return True when a trivial query succeeds."""
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.warning("database readiness check failed", exc_info=True)
        return False
    return True


async def dispose_engine() -> None:
    """Release pooled connections at shutdown."""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
