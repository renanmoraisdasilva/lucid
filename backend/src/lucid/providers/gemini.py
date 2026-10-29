"""Gemini adapter over the Interactions API.

This module is the only place allowed to import ``google.genai`` (enforced by a
test). It maps application contracts to provider calls and provider events to
application events, and translates every failure into a domain error.

Verified against google-genai 2.34.0 on 2026-10-29; see
``docs/architecture/gemini-adapter-notes.md``.
"""

from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
from typing import Any, cast

from google import genai
from google.genai import types

from lucid.domain.enums import Role
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
    ProviderMessage,
    StreamCompleted,
    TextDelta,
    Usage,
)

_STEP_TYPE: dict[Role, str] = {
    Role.USER: "user_input",
    Role.ASSISTANT: "model_output",
}

# Provider stream error codes, mapped to the retry semantics in ADR-005.
_RATE_LIMIT_CODES = frozenset({"resource_exhausted", "rate_limited"})
_TIMEOUT_CODES = frozenset({"gateway_timeout", "deadline_exceeded"})
_UNAVAILABLE_CODES = frozenset({"unavailable", "overloaded", "internal"})
_INVALID_CODES = frozenset(
    {"invalid_argument", "failed_precondition", "not_found", "permission_denied", "unauthenticated"}
)


def to_step(message: ProviderMessage) -> dict[str, object]:
    """Map one history turn to an Interactions API step."""
    return {
        "type": _STEP_TYPE[message.role],
        "content": [{"type": "text", "text": message.content}],
    }


def map_usage(usage: object | None) -> Usage | None:
    """Map provider usage metadata, tolerating absent fields."""
    if usage is None:
        return None

    raw: Mapping[str, object] | None = None
    model_dump = getattr(usage, "model_dump", None)
    if callable(model_dump):
        dumped: object = model_dump()
        if isinstance(dumped, Mapping):
            raw = cast("Mapping[str, object]", dumped)

    return Usage(
        input_tokens=_as_int(getattr(usage, "total_input_tokens", None)),
        output_tokens=_as_int(getattr(usage, "total_output_tokens", None)),
        thought_tokens=_as_int(getattr(usage, "total_thought_tokens", None)),
        total_tokens=_as_int(getattr(usage, "total_tokens", None)),
        raw=raw,
    )


def map_event(event: object) -> ProviderEvent | None:
    """Map a provider stream event, ignoring steps the MVP does not render."""
    kind = getattr(event, "event_type", None)

    if kind == "step.delta":
        delta = getattr(event, "delta", None)
        if getattr(delta, "type", None) != "text":
            return None  # thought_signature, thought_summary, tool arguments
        text = getattr(delta, "text", None)
        if isinstance(text, str) and text:
            return TextDelta(text=text)
        return None

    if kind == "interaction.completed":
        interaction = getattr(event, "interaction", None)
        status = getattr(interaction, "status", None)
        if status in ("failed", "cancelled"):
            raise ProviderStreamError(detail=f"interaction status {status!r}")
        finish_reason = "length" if status == "incomplete" else "stop"
        return StreamCompleted(
            usage=map_usage(getattr(interaction, "usage", None)),
            finish_reason=finish_reason,
        )

    if kind == "error":
        raise _translate_stream_error(getattr(event, "error", None))

    # interaction.created, interaction.status_update, step.start, step.stop
    return None


def classify_exception(error: object) -> ProviderError:
    """Translate any provider-side exception into a domain error.

    Duck-typed on purpose: the SDK's timeout/connection types live in an internal
    module, and status codes are the stable contract.
    """
    status = getattr(error, "status_code", None)
    detail = getattr(error, "message", None) or str(error)

    if isinstance(status, int):
        return _from_status(status, detail)

    name = type(error).__name__
    if name == "APITimeoutError":
        return ProviderTimeout(detail=detail)
    if name == "APIConnectionError":
        return ProviderUnavailable(detail=detail)
    if name in ("ValidationError", "ValueError"):
        return ProviderInvalidRequest("The provider rejected the request shape.", detail=detail)
    return ProviderStreamError(detail=detail)


class GeminiProvider:
    """Streams text from Gemini via the Interactions API."""

    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        max_output_tokens: int = 2048,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )

    async def stream(self, request: GenerationRequest) -> AsyncIterator[ProviderEvent]:
        try:
            stream = await self._client.aio.interactions.create(
                model=request.model or self._model,
                input=[to_step(message) for message in request.messages],
                system_instruction=request.system_prompt,
                generation_config={"max_output_tokens": request.max_output_tokens},
                stream=True,
                store=False,
                automatic_continuation=False,
            )
        except Exception as error:
            raise classify_exception(error) from error

        # The SDK annotates create() as returning Interaction, but stream=True
        # resolves to AsyncStream. Cast once here instead of loosening the module.
        active_stream = cast(Any, stream)

        try:
            async for event in active_stream:
                mapped = map_event(event)
                if mapped is not None:
                    yield mapped
        except ProviderError:
            raise
        except Exception as error:
            raise classify_exception(error) from error
        finally:
            # Early exit (cancellation) leaves the HTTP stream open otherwise.
            # The SDK's close() is a coroutine; CancelError paths are exercised in M4.
            with suppress(Exception):
                await active_stream.close()


def _from_status(status: int, detail: str) -> ProviderError:
    if status == 429:
        return ProviderRateLimited(detail=detail)
    if status in (408, 504):
        return ProviderTimeout(detail=detail)
    if status >= 500:
        return ProviderUnavailable(detail=detail)
    if 400 <= status < 500:
        return ProviderInvalidRequest(detail=detail)
    return ProviderUnavailable(detail=detail)


def _translate_stream_error(error: object | None) -> ProviderError:
    code = getattr(error, "code", None)
    message = getattr(error, "message", None)
    detail = f"{code}: {message}" if code else str(error)

    if isinstance(code, str):
        if code in _RATE_LIMIT_CODES:
            return ProviderRateLimited(detail=detail)
        if code in _TIMEOUT_CODES:
            return ProviderTimeout(detail=detail)
        if code in _UNAVAILABLE_CODES:
            return ProviderUnavailable(detail=detail)
        if code in _INVALID_CODES:
            return ProviderInvalidRequest(detail=detail)
    return ProviderStreamError(detail=detail)


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None
