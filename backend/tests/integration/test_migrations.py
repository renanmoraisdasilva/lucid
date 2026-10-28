"""Migration chain integrity: downgrade/upgrade and model drift."""

import asyncio

from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.support import alembic_config

CHAT_TABLES = ("conversations", "messages", "generation_attempts")


async def _existing_tables(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        return {row[0] for row in result}


async def test_downgrade_removes_chat_tables(engine: AsyncEngine) -> None:
    await asyncio.to_thread(command.downgrade, alembic_config(), "base")

    remaining = await _existing_tables(engine)

    assert remaining.isdisjoint(CHAT_TABLES)

    await asyncio.to_thread(command.upgrade, alembic_config(), "head")


async def test_upgrade_recreates_chat_tables(engine: AsyncEngine) -> None:
    tables = await _existing_tables(engine)

    assert set(CHAT_TABLES).issubset(tables)
    assert "alembic_version" in tables


async def test_models_match_the_migration(engine: AsyncEngine) -> None:
    """Fails when a model change was not captured in a migration."""
    await asyncio.to_thread(command.check, alembic_config())
