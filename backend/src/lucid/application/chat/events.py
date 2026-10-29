"""SSE payload construction for one generation attempt."""

import uuid

from lucid.application.chat.turns import PreparedGeneration
from lucid.domain.enums import AttemptStatus
from lucid.domain.errors import ProviderError
from lucid.domain.provider import Usage

GenerationEvent = tuple[str, dict[str, object]]


def meta_event(prepared: PreparedGeneration, model: str) -> GenerationEvent:
    return (
        "meta",
        {
            "conversation_id": str(prepared.conversation_id),
            "conversation_title": prepared.conversation_title,
            "user_message_id": str(prepared.user_message_id),
            "attempt_id": str(prepared.attempt_id),
            "model": model,
            "is_new_conversation": prepared.is_new_conversation,
        },
    )


def usage_event(usage: Usage) -> GenerationEvent:
    return (
        "usage",
        {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "thought_tokens": usage.thought_tokens,
            "total_tokens": usage.total_tokens,
        },
    )


def done_event(
    prepared: PreparedGeneration,
    status: AttemptStatus,
    assistant_message_id: uuid.UUID | None,
    finish_reason: str,
) -> GenerationEvent:
    return (
        "done",
        {
            "attempt_id": str(prepared.attempt_id),
            "status": status.value,
            "assistant_message_id": optional_id(assistant_message_id),
            "finish_reason": finish_reason,
        },
    )


def error_event(
    prepared: PreparedGeneration,
    error: ProviderError,
    assistant_message_id: uuid.UUID | None,
) -> GenerationEvent:
    return (
        "error",
        {
            "code": error.code,
            "message": str(error),
            "retryable": error.retryable,
            "attempt_id": str(prepared.attempt_id),
            "assistant_message_id": optional_id(assistant_message_id),
            "retry_after_seconds": error.retry_after_seconds,
        },
    )


def optional_id(value: uuid.UUID | None) -> str | None:
    return str(value) if value is not None else None
