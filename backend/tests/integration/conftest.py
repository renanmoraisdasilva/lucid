"""Integration fixtures: real PostgreSQL, real migrations.

These tests TRUNCATE the chat tables between cases. Point them at a disposable
database (the Docker Compose ``db`` service by default). Override with
TEST_DATABASE_URL.
"""

import asyncio
import os

# Must run before importing anything from `lucid`: settings are cached on first
# use and read the developer's .env, which may target a different database.
from tests.integration.support import database_url

os.environ["DATABASE_URL"] = database_url()

from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from lucid.application.cooldown import RateLimitCooldown
from lucid.application.registry import GenerationRegistry
from lucid.config import get_settings
from lucid.main import create_app
from lucid.persistence.db import get_session
from tests.integration.support import alembic_config


@pytest.fixture(scope="session")
def engine() -> Iterator[AsyncEngine]:
    """A migrated database engine, or a skip if no database is reachable.

    Deliberately synchronous: the engine is loop-agnostic with NullPool, and
    running migrations here would otherwise nest asyncio.run inside a test loop.
    """
    url = database_url()
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    test_engine = create_async_engine(url, poolclass=NullPool)

    try:
        asyncio.run(_prepare_database(test_engine))
    except Exception as error:  # pragma: no cover - environment dependent
        asyncio.run(test_engine.dispose())
        pytest.skip(f"PostgreSQL is not reachable at {url}: {error}")

    yield test_engine
    asyncio.run(test_engine.dispose())


async def _prepare_database(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    await asyncio.to_thread(command.downgrade, alembic_config(), "base")
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")


@pytest.fixture(autouse=True)
async def _clean_database(engine: AsyncEngine) -> AsyncIterator[None]:
    """Empty the chat tables after every test, whatever fixtures it used."""
    yield
    async with engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE conversations, generation_attempts, messages CASCADE")
        )


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session scoped to one test."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db_session:
        yield db_session
        await db_session.rollback()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory bound to the test engine, used by the streaming path."""
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def app(engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    """The real application with its database session pointed at the test engine."""
    application = create_app()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as db_session:
            yield db_session

    application.dependency_overrides[get_session] = override_get_session
    application.state.session_factory = session_factory
    application.state.registry = GenerationRegistry()
    application.state.cooldown = RateLimitCooldown()
    return application


@pytest.fixture
async def api_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """HTTP client bound to the app, using the test database."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
