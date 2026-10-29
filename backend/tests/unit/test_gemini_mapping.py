"""Gemini adapter mapping and error translation, without network access."""

from types import SimpleNamespace

import pytest

from lucid.domain.enums import Role
from lucid.domain.errors import (
    ProviderInvalidRequest,
    ProviderRateLimited,
    ProviderStreamError,
    ProviderTimeout,
    ProviderUnavailable,
)
from lucid.domain.provider import ProviderMessage, StreamCompleted, TextDelta
from lucid.providers.gemini import (
    build_generation_config,
    classify_exception,
    map_event,
    map_usage,
    to_step,
)


def _delta(delta_type: str, text: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        event_type="step.delta", delta=SimpleNamespace(type=delta_type, text=text)
    )


def _completed(status: str, usage: object | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        event_type="interaction.completed",
        interaction=SimpleNamespace(status=status, usage=usage),
    )


def _error(code: str, message: str = "boom") -> SimpleNamespace:
    return SimpleNamespace(event_type="error", error=SimpleNamespace(code=code, message=message))


def test_user_message_maps_to_user_input_step() -> None:
    step = to_step(ProviderMessage(role=Role.USER, content="hello"))

    assert step == {"type": "user_input", "content": [{"type": "text", "text": "hello"}]}


def test_assistant_message_maps_to_model_output_step() -> None:
    step = to_step(ProviderMessage(role=Role.ASSISTANT, content="hi"))

    assert step == {"type": "model_output", "content": [{"type": "text", "text": "hi"}]}


def test_generation_config_always_caps_output() -> None:
    config = build_generation_config(max_output_tokens=512, thinking_level=None)

    assert config == {"max_output_tokens": 512}


def test_generation_config_sets_thinking_level() -> None:
    """Regression: the provider default spent ~25s before the first token."""
    config = build_generation_config(max_output_tokens=512, thinking_level="low")

    assert config == {"max_output_tokens": 512, "thinking_level": "low"}


def test_generation_config_omits_blank_thinking_level() -> None:
    assert "thinking_level" not in build_generation_config(max_output_tokens=64, thinking_level="")


def test_text_delta_is_mapped() -> None:
    mapped = map_event(_delta("text", "pong"))

    assert isinstance(mapped, TextDelta)
    assert mapped.text == "pong"


def test_thought_and_empty_deltas_are_ignored() -> None:
    assert map_event(_delta("thought_signature")) is None
    assert map_event(_delta("text", "")) is None


def test_non_terminal_events_are_ignored() -> None:
    assert map_event(SimpleNamespace(event_type="step.start")) is None
    assert map_event(SimpleNamespace(event_type="interaction.status_update")) is None
    assert map_event(SimpleNamespace(event_type="interaction.created")) is None


def test_completion_carries_usage() -> None:
    usage = SimpleNamespace(
        total_input_tokens=11,
        total_output_tokens=7,
        total_thought_tokens=3,
        total_tokens=21,
        model_dump=lambda: {"total_tokens": 21},
    )

    mapped = map_event(_completed("completed", usage))

    assert isinstance(mapped, StreamCompleted)
    assert mapped.usage is not None
    assert mapped.usage.input_tokens == 11
    assert mapped.usage.output_tokens == 7
    assert mapped.usage.thought_tokens == 3
    assert mapped.usage.total_tokens == 21
    assert mapped.usage.raw == {"total_tokens": 21}


def test_completion_without_usage_is_allowed() -> None:
    mapped = map_event(_completed("completed", None))

    assert isinstance(mapped, StreamCompleted)
    assert mapped.usage is None


def test_failed_interaction_raises() -> None:
    with pytest.raises(ProviderStreamError):
        map_event(_completed("failed", None))


def test_usage_mapping_handles_missing_object() -> None:
    assert map_usage(None) is None


def test_usage_mapping_exposes_unknown_fields_as_none() -> None:
    usage = map_usage(SimpleNamespace(total_input_tokens=None, total_output_tokens=4))

    assert usage is not None
    assert usage.input_tokens is None
    assert usage.output_tokens == 4
    assert usage.total_tokens is None


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("resource_exhausted", ProviderRateLimited),
        ("gateway_timeout", ProviderTimeout),
        ("unavailable", ProviderUnavailable),
        ("overloaded", ProviderUnavailable),
        ("invalid_argument", ProviderInvalidRequest),
        ("not_found", ProviderInvalidRequest),
        ("something_else", ProviderStreamError),
    ],
)
def test_stream_error_codes_map_to_domain_errors(code: str, expected: type[Exception]) -> None:
    with pytest.raises(expected):
        map_event(_error(code))


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, ProviderRateLimited),
        (408, ProviderTimeout),
        (504, ProviderTimeout),
        (500, ProviderUnavailable),
        (503, ProviderUnavailable),
        (400, ProviderInvalidRequest),
        (401, ProviderInvalidRequest),
        (404, ProviderInvalidRequest),
    ],
)
def test_http_status_maps_to_domain_errors(status: int, expected: type[Exception]) -> None:
    error = SimpleNamespace(status_code=status, message="provider said no")

    translated = classify_exception(error)  # type: ignore[arg-type]

    assert isinstance(translated, expected)
    assert translated.detail == "provider said no"


def test_rate_limit_message_retry_hint_is_parsed() -> None:
    error = SimpleNamespace(
        status_code=429,
        message="Error code: 429 - {'error': {'message': 'Please retry in 21.2s.'}}",
    )

    translated = classify_exception(error)  # type: ignore[arg-type]

    assert isinstance(translated, ProviderRateLimited)
    assert translated.retry_after_seconds == 21.2


def test_rate_limit_retry_delay_field_is_parsed() -> None:
    error = SimpleNamespace(
        status_code=429,
        message='{"error": {"details": [{"retryDelay": "7s"}]}}',
    )

    translated = classify_exception(error)  # type: ignore[arg-type]

    assert isinstance(translated, ProviderRateLimited)
    assert translated.retry_after_seconds == 7.0


def test_compound_duration_hint_is_parsed() -> None:
    """Real free-tier payload: "Please retry in 11h2m40s"."""
    error = SimpleNamespace(
        status_code=429,
        message=(
            "Error code: 429 - {'error': {'message': 'Rate limit exceeded for model "
            "gemini-3.6-flash (limit: 20 requests per day on Free Tier). Please retry "
            "in 11h2m40s or upgrade your tier.'}}"
        ),
    )

    translated = classify_exception(error)  # type: ignore[arg-type]

    assert isinstance(translated, ProviderRateLimited)
    assert translated.retry_after_seconds == 39760.0


def test_daily_limit_gets_an_actionable_message() -> None:
    error = SimpleNamespace(
        status_code=429,
        message="Rate limit exceeded (limit: 20 requests per day on Free Tier).",
    )

    translated = classify_exception(error)  # type: ignore[arg-type]

    assert "daily limit" in str(translated)


def test_rate_limit_without_hint_has_no_wait() -> None:
    error = SimpleNamespace(status_code=429, message="quota exceeded")

    translated = classify_exception(error)  # type: ignore[arg-type]

    assert isinstance(translated, ProviderRateLimited)
    assert translated.retry_after_seconds is None


def test_timeout_class_name_is_recognised() -> None:
    class APITimeoutError(Exception):
        pass

    translated = classify_exception(APITimeoutError("timed out"))

    assert isinstance(translated, ProviderTimeout)
    assert translated.retryable is True


def test_connection_class_name_is_recognised() -> None:
    class APIConnectionError(Exception):
        pass

    assert isinstance(classify_exception(APIConnectionError("reset")), ProviderUnavailable)


def test_validation_error_is_not_retryable() -> None:
    translated = classify_exception(ValueError("bad shape"))

    assert isinstance(translated, ProviderInvalidRequest)
    assert translated.retryable is False


def test_unknown_error_is_a_stream_error() -> None:
    assert isinstance(classify_exception(RuntimeError("???")), ProviderStreamError)


def test_provider_messages_never_contain_internal_details() -> None:
    translated = classify_exception(
        SimpleNamespace(status_code=500, message="internal stack trace detail")
    )

    assert "stack trace" not in str(translated)
    assert translated.detail is not None
