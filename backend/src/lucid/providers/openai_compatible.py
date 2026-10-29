"""OpenAI-compatible chat provider.

Covers any endpoint that speaks ``POST /chat/completions`` with SSE streaming:
Groq, Cerebras, OpenRouter, Mistral, GitHub Models, and local Ollama/vLLM. The
provider boundary means the application never learns which of them is in use.
"""

import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Any, cast

import httpx

from lucid.domain.durations import parse_duration, parse_retry_after
from lucid.domain.errors import (
    ProviderError,
    ProviderInvalidRequest,
    ProviderRateLimited,
    ProviderStreamError,
    ProviderTimeout,
    ProviderUnavailable,
)
from lucid.domain.provider import (
    GenerationRequest,
    ProviderEvent,
    StreamCompleted,
    TextDelta,
    Usage,
)

_REQUEST_DETAIL_LIMIT = 500


class OpenAICompatibleProvider:
    """Streams text from an OpenAI-compatible endpoint."""

    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 60.0,
        max_output_tokens: int = 2048,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._max_output_tokens = max_output_tokens
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def stream(self, request: GenerationRequest) -> AsyncIterator[ProviderEvent]:
        state = _StreamState()
        try:
            async with self._client.stream(
                "POST",
                self._endpoint,
                json=self._payload(request),
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")
                    raise classify_status(response.status_code, body, response.headers)

                async for line in response.aiter_lines():
                    texts = state.feed(line)
                    if texts is None:
                        break
                    for text in texts:
                        yield TextDelta(text=text)
        except ProviderError:
            raise
        except httpx.TimeoutException as error:
            raise ProviderTimeout(detail=str(error)) from error
        except httpx.HTTPError as error:
            raise ProviderUnavailable(detail=str(error)) from error
        except json.JSONDecodeError as error:
            raise ProviderStreamError(detail="malformed stream frame") from error

        yield StreamCompleted(usage=state.usage)

    def _payload(self, request: GenerationRequest) -> dict[str, Any]:
        return {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                *(
                    {"role": message.role.value, "content": message.content}
                    for message in request.messages
                ),
            ],
            "stream": True,
            "max_tokens": request.max_output_tokens or self._max_output_tokens,
            "stream_options": {"include_usage": True},
        }


@dataclass
class _StreamState:
    """Accumulates usage while turning SSE lines into text deltas."""

    usage: Usage | None = None

    def feed(self, line: str) -> list[str] | None:
        """Text deltas for this line, or ``None`` when the provider is done."""
        if not line.startswith("data:"):
            return []
        data = line.removeprefix("data:").strip()
        if not data:
            return []
        if data == "[DONE]":
            return None

        chunk = json.loads(data)
        raw_usage = chunk.get("usage")
        if isinstance(raw_usage, Mapping):
            self.usage = map_usage(cast("Mapping[str, Any]", raw_usage))
        return _texts(chunk)


def classify_status(status: int, body: str, headers: Mapping[str, str]) -> ProviderError:
    """Map an HTTP failure to a domain error, keeping the wait hint."""
    detail = body[:_REQUEST_DETAIL_LIMIT]

    if status == 429:
        retry_after = parse_retry_after(headers.get("retry-after")) or parse_duration(body)
        daily = "per day" in body.lower() or "daily" in body.lower()
        return ProviderRateLimited(
            (
                "The free-tier daily limit is reached. Try again later, switch the "
                "model, or upgrade the tier."
                if daily
                else None
            ),
            detail=detail,
            retry_after_seconds=retry_after,
        )
    if status in (408, 504):
        return ProviderTimeout(detail=detail)
    if status >= 500:
        return ProviderUnavailable(detail=detail)
    if 400 <= status < 500:
        return ProviderInvalidRequest(detail=detail)
    return ProviderUnavailable(detail=detail)


def map_usage(raw: Mapping[str, Any]) -> Usage:
    """Map OpenAI-style usage fields."""
    return Usage(
        input_tokens=_as_int(raw.get("prompt_tokens")),
        output_tokens=_as_int(raw.get("completion_tokens")),
        thought_tokens=None,
        total_tokens=_as_int(raw.get("total_tokens")),
        raw=dict(raw),
    )


def _texts(chunk: Mapping[str, Any]) -> list[str]:
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return []
    items = cast("list[object]", choices)
    first = items[0]
    if not isinstance(first, Mapping):
        return []
    delta: object = cast("Mapping[str, Any]", first).get("delta")
    if not isinstance(delta, Mapping):
        return []
    content: object = cast("Mapping[str, Any]", delta).get("content")
    return [content] if isinstance(content, str) and content else []


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None
