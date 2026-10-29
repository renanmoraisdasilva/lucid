"""Provider selection from configuration."""

from collections.abc import Awaitable, Callable
from typing import cast

from lucid.config import Settings
from lucid.domain.errors import ConfigurationError
from lucid.domain.provider import ChatProvider
from lucid.providers.fake import FakeProvider
from lucid.providers.gemini import GeminiProvider
from lucid.providers.openai_compatible import OpenAICompatibleProvider


def build_provider(settings: Settings, provider: str | None = None) -> ChatProvider:
    """Build one provider by name (default: the configured one)."""
    name = provider or settings.provider

    if name == "fake":
        return FakeProvider()

    if name == "gemini":
        if settings.gemini_api_key is None:
            raise ConfigurationError(
                "GEMINI_API_KEY is required for the Gemini provider. "
                "Set it in .env, or use another provider."
            )
        return GeminiProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            timeout_seconds=settings.generation_timeout_seconds,
            max_output_tokens=settings.generation_max_output_tokens,
            thinking_level=settings.gemini_thinking_level,
        )

    if name == "openai_compatible":
        if settings.openai_api_key is None:
            raise ConfigurationError(
                "OPENAI_API_KEY (or GROQ_API_KEY) is required for the "
                "OpenAI-compatible provider. Set it in .env."
            )
        return OpenAICompatibleProvider(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key.get_secret_value(),
            timeout_seconds=settings.generation_timeout_seconds,
            max_output_tokens=settings.generation_max_output_tokens,
        )

    raise ConfigurationError(f"Unknown provider: {name!r}")


class ProviderRegistry:
    """Builds providers lazily and reuses one instance per provider name."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._providers: dict[str, ChatProvider] = {}

    def get(self, name: str) -> ChatProvider:
        provider = self._providers.get(name)
        if provider is None:
            provider = build_provider(self._settings, name)
            self._providers[name] = provider
        return provider

    def override(self, name: str, provider: ChatProvider) -> None:
        """Inject a provider, used by tests."""
        self._providers[name] = provider

    async def aclose(self) -> None:
        for provider in self._providers.values():
            close = getattr(provider, "aclose", None)
            if callable(close):
                await cast("Callable[[], Awaitable[None]]", close)()
