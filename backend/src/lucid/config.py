"""Application settings, loaded from environment variables and .env files."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
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

    provider: Literal["gemini", "openai_compatible", "fake"] = Field(
        default="openai_compatible",
        description="Default ChatProvider implementation.",
    )
    gemini_api_key: SecretStr | None = Field(default=None, description="Gemini credential.")
    gemini_model: str = Field(default="gemini-3.6-flash", description="Gemini model identifier.")
    generation_timeout_seconds: float = Field(
        default=60.0,
        gt=0,
        le=600,
        validation_alias=AliasChoices("GENERATION_TIMEOUT_SECONDS", "GEMINI_TIMEOUT_SECONDS"),
    )
    generation_max_output_tokens: int = Field(
        default=2048,
        ge=1,
        le=8192,
        validation_alias=AliasChoices("GENERATION_MAX_OUTPUT_TOKENS", "GEMINI_MAX_OUTPUT_TOKENS"),
    )
    gemini_thinking_level: Literal["minimal", "low", "medium", "high"] | None = Field(
        default="low",
        description=(
            "Provider reasoning effort. 'low' cuts first-token latency from ~25s to "
            "under a second on the flash-lite models. Set to 'high' for harder questions."
        ),
    )

    openai_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Any OpenAI-compatible endpoint (Groq, Cerebras, OpenRouter, Ollama).",
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "GROQ_API_KEY"),
        description="OpenAI-compatible credential (either env name is accepted).",
    )
    openai_models: str = Field(
        default="openai/gpt-oss-120b,openai/gpt-oss-20b,qwen/qwen3.8-27b",
        description="Comma-separated model ids offered by the picker for this endpoint.",
    )
    openai_model: str | None = Field(
        default=None,
        description="Default model for this endpoint; falls back to the first listed.",
    )

    context_max_input_tokens: int = Field(
        default=6_000,
        ge=1_000,
        description=(
            "History + system prompt budget. Kept under Groq's free-tier 8K TPM; "
            "raise it for Gemini or a paid tier."
        ),
    )
    context_reserved_output_tokens: int = Field(default=4_096, ge=0)
    context_safety_margin_tokens: int = Field(default=512, ge=0)
    context_max_messages: int = Field(default=60, ge=1, le=1_000)

    generation_max_retries: int = Field(default=2, ge=0, le=5)
    retry_base_delay_ms: int = Field(default=1_000, ge=1)
    retry_max_delay_ms: int = Field(default=8_000, ge=1)
    retry_jitter: bool = True
    generation_first_token_timeout_seconds: float = Field(
        default=50.0,
        gt=0,
        le=120,
        description=(
            "Abort a provider call that has produced no text within this window, so a "
            "queued request fails with a retryable error instead of waiting blank. "
            "Free-tier queueing has been measured at 30-40s."
        ),
    )

    reconcile_on_startup: bool = True

    system_prompt_path: Path = Field(default=BACKEND_DIR / "prompts" / "system.md")

    @property
    def openai_model_list(self) -> list[str]:
        """Model ids offered by the OpenAI-compatible endpoint."""
        models = [model.strip() for model in self.openai_models.split(",") if model.strip()]
        return models or ["openai/gpt-oss-120b"]

    @property
    def default_openai_model(self) -> str:
        """The endpoint's default model, falling back to the first listed."""
        if self.openai_model and self.openai_model in self.openai_model_list:
            return self.openai_model
        return self.openai_model_list[0]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
