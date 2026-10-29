"""Application settings, loaded from environment variables and .env files."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime configuration.

    The repository-root `.env` is loaded first and `backend/.env` second, so a
    local override next to the code wins without duplicating every value.
    """

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://lucid:lucid@localhost:5432/lucid",
        description="SQLAlchemy async database URL.",
    )
    log_level: str = Field(default="INFO", description="Root log level.")
    app_env: str = Field(default="local", description="Environment label for logs.")

    provider: Literal["gemini", "fake"] = Field(
        default="gemini",
        description="Which ChatProvider implementation to use.",
    )
    gemini_api_key: SecretStr | None = Field(default=None, description="Provider credential.")
    gemini_model: str = Field(default="gemini-3.5-flash-lite", description="Model identifier.")
    gemini_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    gemini_max_output_tokens: int = Field(default=2048, ge=1, le=8192)

    system_prompt_path: Path = Field(default=BACKEND_DIR / "prompts" / "system.md")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
