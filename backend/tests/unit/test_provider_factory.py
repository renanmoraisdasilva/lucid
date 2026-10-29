"""Provider selection from settings."""

import pytest

from lucid.config import Settings
from lucid.domain.errors import ConfigurationError
from lucid.providers.factory import build_provider
from lucid.providers.fake import FakeProvider
from lucid.providers.gemini import GeminiProvider


def _settings(**overrides: object) -> Settings:
    # _env_file=None keeps the developer's real .env out of these assertions.
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_fake_provider_is_selected() -> None:
    provider = build_provider(_settings(provider="fake"))

    assert isinstance(provider, FakeProvider)
    assert provider.name == "fake"


def test_gemini_without_key_fails_fast() -> None:
    with pytest.raises(ConfigurationError):
        build_provider(_settings(provider="gemini", gemini_api_key=None))


def test_gemini_with_key_is_constructed() -> None:
    provider = build_provider(
        _settings(provider="gemini", gemini_api_key="test-key", gemini_model="test-model")
    )

    assert isinstance(provider, GeminiProvider)
    assert provider.name == "gemini"


def test_defaults_match_the_spec() -> None:
    settings = _settings()

    assert settings.provider == "gemini"
    assert settings.gemini_model == "gemini-3.5-flash-lite"
    assert settings.gemini_max_output_tokens == 2048
    assert settings.gemini_timeout_seconds == 60.0


def test_system_prompt_path_defaults_inside_the_backend() -> None:
    settings = _settings()

    assert settings.system_prompt_path.name == "system.md"
    assert settings.system_prompt_path.parent.name == "prompts"
