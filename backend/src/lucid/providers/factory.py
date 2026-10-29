"""Provider selection from configuration."""

from typing import assert_never

from lucid.config import Settings
from lucid.domain.errors import ConfigurationError
from lucid.domain.provider import ChatProvider
from lucid.providers.fake import FakeProvider
from lucid.providers.gemini import GeminiProvider


def build_provider(settings: Settings) -> ChatProvider:
    """Build the configured provider, failing fast on missing credentials."""
    if settings.provider == "fake":
        return FakeProvider()
    if settings.provider == "gemini":
        if settings.gemini_api_key is None:
            raise ConfigurationError(
                "GEMINI_API_KEY is required when PROVIDER=gemini. "
                "Set it in .env, or set PROVIDER=fake for offline development."
            )
        return GeminiProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
            max_output_tokens=settings.gemini_max_output_tokens,
        )
    assert_never(settings.provider)
