"""OpenAI-compatible adapter, exercised through a mocked HTTP transport."""

import json
from typing import Any

import httpx
import pytest

from lucid.domain.enums import Role
from lucid.domain.errors import (
    ProviderInvalidRequest,
    ProviderRateLimited,
    ProviderTimeout,
    ProviderUnavailable,
)
from lucid.domain.provider import (
    GenerationRequest,
    ProviderEvent,
    ProviderMessage,
    StreamCompleted,
    TextDelta,
)
from lucid.providers.openai_compatible import OpenAICompatibleProvider, map_usage

BASE_URL = "https://api.groq.com/openai/v1"


def _request() -> GenerationRequest:
    return GenerationRequest(
        model="openai/gpt-oss-120b",
        system_prompt="Be brief.",
        messages=[
            ProviderMessage(role=Role.USER, content="Hello"),
            ProviderMessage(role=Role.ASSISTANT, content="Hi"),
            ProviderMessage(role=Role.USER, content="Again"),
        ],
        max_output_tokens=64,
        request_id="req-1",
    )


def _sse(*chunks: Any) -> bytes:
    lines = [f"data: {json.dumps(chunk)}\n\n" for chunk in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def _provider(handler: httpx.AsyncBaseTransport) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url=BASE_URL,
        api_key="test-key",
        client=httpx.AsyncClient(transport=handler),
    )


async def _collect(provider: OpenAICompatibleProvider) -> list[ProviderEvent]:
    return [event async for event in provider.stream(_request())]


async def test_streams_text_and_usage() -> None:
    body = _sse(
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
        {
            "choices": [{"delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 2, "total_tokens": 13},
        },
    )
    provider = _provider(httpx.MockTransport(lambda request: httpx.Response(200, content=body)))

    events = await _collect(provider)

    deltas = [event for event in events if isinstance(event, TextDelta)]
    assert [delta.text for delta in deltas] == ["Hel", "lo"]
    completion = events[-1]
    assert isinstance(completion, StreamCompleted)
    assert completion.usage is not None
    assert completion.usage.input_tokens == 11
    assert completion.usage.output_tokens == 2
    assert completion.usage.total_tokens == 13


async def test_sends_system_prompt_and_history() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, content=_sse({"choices": [{"delta": {"content": "ok"}}]}))

    provider = _provider(httpx.MockTransport(handler))

    await _collect(provider)

    assert seen["model"] == "openai/gpt-oss-120b"
    assert seen["stream"] is True
    assert seen["max_tokens"] == 64
    messages = seen["messages"]
    assert isinstance(messages, list)
    assert messages[0] == {"role": "system", "content": "Be brief."}
    assert messages[1] == {"role": "user", "content": "Hello"}
    assert messages[-1] == {"role": "user", "content": "Again"}


async def test_missing_usage_is_reported_as_unknown() -> None:
    body = _sse({"choices": [{"delta": {"content": "ok"}}]})
    provider = _provider(httpx.MockTransport(lambda request: httpx.Response(200, content=body)))

    events = await _collect(provider)

    completion = events[-1]
    assert isinstance(completion, StreamCompleted)
    assert completion.usage is None


async def test_rate_limit_uses_the_retry_after_header() -> None:
    handler = httpx.MockTransport(
        lambda request: httpx.Response(
            429,
            headers={"retry-after": "30"},
            json={"error": {"message": "Rate limit reached for model"}},
        )
    )
    provider = _provider(handler)

    with pytest.raises(ProviderRateLimited) as raised:
        await _collect(provider)

    assert raised.value.retry_after_seconds == 30.0


async def test_rate_limit_parses_a_duration_in_the_body() -> None:
    handler = httpx.MockTransport(
        lambda request: httpx.Response(
            429,
            json={"error": {"message": "You have exceeded your daily quota. Try again in 2m30s."}},
        )
    )
    provider = _provider(handler)

    with pytest.raises(ProviderRateLimited) as raised:
        await _collect(provider)

    assert raised.value.retry_after_seconds == 150.0
    assert raised.value.retryable is True


async def test_daily_limit_message_is_actionable() -> None:
    handler = httpx.MockTransport(
        lambda request: httpx.Response(
            429, json={"error": {"message": "Daily limit reached (1000 per day)"}}
        )
    )
    provider = _provider(handler)

    with pytest.raises(ProviderRateLimited) as raised:
        await _collect(provider)

    assert "daily limit" in str(raised.value)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (500, ProviderUnavailable),
        (503, ProviderUnavailable),
        (400, ProviderInvalidRequest),
        (401, ProviderInvalidRequest),
    ],
)
async def test_http_errors_map_to_domain_errors(status: int, expected: type[Exception]) -> None:
    handler = httpx.MockTransport(lambda request: httpx.Response(status, json={"error": {}}))
    provider = _provider(handler)

    with pytest.raises(expected):
        await _collect(provider)


async def test_connection_errors_are_retryable_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    provider = _provider(httpx.MockTransport(handler))

    with pytest.raises(ProviderUnavailable) as raised:
        await _collect(provider)

    assert raised.value.retryable is True


async def test_timeouts_map_to_provider_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    provider = _provider(httpx.MockTransport(handler))

    with pytest.raises(ProviderTimeout):
        await _collect(provider)


def test_usage_mapping_tolerates_missing_fields() -> None:
    usage = map_usage({"prompt_tokens": 5})

    assert usage.input_tokens == 5
    assert usage.output_tokens is None
    assert usage.total_tokens is None
