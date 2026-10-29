"""Provider-independent request, event, and interface definitions.

No SDK types cross this boundary. The application depends on these dataclasses
and on ``ChatProvider``; the Gemini adapter depends on them too.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from lucid.domain.enums import Role


@dataclass(frozen=True, slots=True)
class ProviderMessage:
    """One turn of history, as the provider needs to see it."""

    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Everything a provider needs for one generation."""

    model: str
    system_prompt: str
    messages: Sequence[ProviderMessage]
    max_output_tokens: int
    request_id: str


@dataclass(frozen=True, slots=True)
class Usage:
    """Token usage. Any field may be unknown."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    thought_tokens: int | None = None
    total_tokens: int | None = None
    raw: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class TextDelta:
    """Incremental assistant text."""

    text: str


@dataclass(frozen=True, slots=True)
class StreamCompleted:
    """Terminal event for a successful generation."""

    usage: Usage | None = None
    finish_reason: str = "stop"


ProviderEvent = TextDelta | StreamCompleted


@runtime_checkable
class ChatProvider(Protocol):
    """Minimal streaming interface the application depends on."""

    name: str

    def stream(self, request: GenerationRequest) -> AsyncIterator[ProviderEvent]: ...
