"""Provider selection and the model catalogue."""

import pytest

from lucid.application.models import build_catalog
from lucid.config import Settings
from lucid.domain.errors import ConfigurationError
from lucid.providers.factory import ProviderRegistry, build_provider
from lucid.providers.fake import FakeProvider
from lucid.providers.gemini import GeminiProvider
from lucid.providers.openai_compatible import OpenAICompatibleProvider


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


def test_openai_compatible_without_key_fails_fast() -> None:
    with pytest.raises(ConfigurationError):
        build_provider(_settings(provider="openai_compatible", openai_api_key=None))


def test_openai_compatible_with_key_is_constructed() -> None:
    provider = build_provider(_settings(provider="openai_compatible", openai_api_key="test-key"))

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "openai_compatible"


def test_groq_env_name_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "from-groq-env")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "from-groq-env"


def test_registry_caches_one_instance_per_provider() -> None:
    registry = ProviderRegistry(_settings(provider="fake"))

    assert registry.get("fake") is registry.get("fake")


def test_defaults_match_the_new_provider_direction() -> None:
    settings = _settings()

    assert settings.provider == "openai_compatible"
    assert settings.openai_base_url.startswith("https://api.groq.com")
    assert "openai/gpt-oss-120b" in settings.openai_model_list
    assert settings.generation_max_output_tokens == 2048
    assert settings.generation_timeout_seconds == 60.0
    assert settings.gemini_thinking_level == "low"
    assert settings.generation_first_token_timeout_seconds == 50.0
    assert settings.context_max_input_tokens == 6_000


def test_catalog_offers_only_configured_providers() -> None:
    settings = _settings(
        provider="openai_compatible",
        openai_api_key="test-key",
        gemini_api_key=None,
        openai_models="openai/gpt-oss-120b,openai/gpt-oss-20b",
    )

    catalog = build_catalog(settings)

    assert [option.id for option in catalog.options] == [
        "openai:openai/gpt-oss-120b",
        "openai:openai/gpt-oss-20b",
    ]
    assert catalog.default_id == "openai:openai/gpt-oss-120b"


def test_catalog_includes_both_when_both_are_configured() -> None:
    catalog = build_catalog(
        _settings(openai_api_key="k", gemini_api_key="g", openai_models="openai/gpt-oss-20b")
    )

    ids = [option.id for option in catalog.options]

    assert "openai:openai/gpt-oss-20b" in ids
    assert any(option.startswith("gemini:") for option in ids)


def test_catalog_falls_back_to_fake_when_nothing_is_configured() -> None:
    catalog = build_catalog(_settings(provider="fake", openai_api_key=None, gemini_api_key=None))

    assert catalog.default_id == "fake:fake-model"
