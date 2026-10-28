"""Application settings, loaded from the environment and an optional .env file."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Only settings that are actually used belong here. Provider and context
    settings are added by the milestones that introduce them.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://chatbot:chatbot@localhost:5432/chatbot",
        description="SQLAlchemy async database URL.",
    )
    log_level: str = Field(default="INFO", description="Root log level.")
    app_env: str = Field(default="local", description="Environment label for logs.")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
