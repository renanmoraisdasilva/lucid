"""Shared helpers for integration tests."""

import os
from pathlib import Path

from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "postgresql+asyncpg://chatbot:chatbot@localhost:5432/chatbot"


def database_url() -> str:
    """Resolve the database under test."""
    return (
        os.environ.get("TEST_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or DEFAULT_DATABASE_URL
    )


def alembic_config() -> Config:
    """Alembic configuration pointed at the database under test."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url())
    return config
