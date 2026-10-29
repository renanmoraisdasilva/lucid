"""Streaming chat orchestration.

Responsibilities:

- prepare a turn (conversation, user message, attempt) and commit it before the
  provider is called;
- stream provider events as application events, buffering text in memory;
- persist the terminal state in one transaction *before* the terminal event, so a
  client that reacts to ``done`` can re-fetch and see the message;
- finalize as ``interrupted`` on stop and client disconnect, including when the
  task has already been cancelled (the write is shielded).
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.application.registry import GenerationRegistry
from lucid.domain.enums import AttemptStatus, Role
from lucid.domain.errors import ProviderError
from lucid.domain.provider import (
    ChatProvider,
    GenerationRequest,
    ProviderMessage,
    TextDelta,
    Usage,
)
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)

GenerationEvent = tuple[str, dict[str, object]]


class ConversationNotFoundError(LookupError):
    """The requested conversation does not exist."""


class MessageNotFoundError(LookupError):
    """The requested message does not exist in that conversation."""


class GenerationInProgressError(RuntimeError):
    """A generation is already running for this conversation."""

    def __init__(self, attempt_id: uuid.UUID) -> None:
        super().__init__("A response is already being generated for this conversation.")
        self.attempt_id = attempt_id


class GenerationAlreadyCompletedError(RuntimeError):
    """Retry requested for a message that already has a completed response."""


@dataclass(frozen=True, slots=True)
class PreparedGeneration:
    """Everything the stream needs, created before the response starts."""

    conversation_id: uuid.UUID
    conversation_title: str
    user_message_id: uuid.UUID
    attempt_id: uuid.UUID
    is_new_conversation: bool


@dataclass(frozen=True, slots=True)
class FinalizedTurn:
    """What the terminal transaction wrote."""

    status: AttemptStatus
    assistant_message_id: uuid.UUID | None
    content: str


async def prepare_message(
    session: AsyncSession,
    *,
    content: str,
    conversation_id: uuid.UUID | None,
    provider_name: str,
    model: str,
) -> PreparedGeneration:
    """Create or continue a conversation and open a generation attempt."""
    conversations = ConversationRepository(session)
    messages = MessageRepository(session)
    attempts = AttemptRepository(session)

    if conversation_id is None:
        conversation = await conversations.create(first_message=content)
        is_new = True
    else:
        conversation = await conversations.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(str(conversation_id))
        is_new = False

    active = await attempts.get_active_for_conversation(conversation.id)
    if active is not None:
        raise GenerationInProgressError(active.id)

    user_message = await messages.append(
        conversation_id=conversation.id, role=Role.USER, content=content
    )
    try:
        attempt = await attempts.create(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            provider=provider_name,
            model=model,
        )
        await conversations.touch(conversation.id)
        await session.commit()
    except IntegrityError as error:
        # The partial unique index rejected a concurrent attempt.
        await session.rollback()
        active = await attempts.get_active_for_conversation(conversation.id)
        if active is not None:
            raise GenerationInProgressError(active.id) from error
        raise

    return PreparedGeneration(
        conversation_id=conversation.id,
        conversation_title=conversation.title,
        user_message_id=user_message.id,
        attempt_id=attempt.id,
        is_new_conversation=is_new,
    )


async def prepare_retry(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    provider_name: str,
    model: str,
) -> PreparedGeneration:
    """Open a new attempt for an existing user message. Never duplicates it."""
    conversations = ConversationRepository(session)
    messages = MessageRepository(session)
    attempts = AttemptRepository(session)

    conversation = await conversations.get(conversation_id)
    if conversation is None:
        raise ConversationNotFoundError(str(conversation_id))

    message = await messages.get(message_id)
    if message is None or message.conversation_id != conversation_id:
        raise MessageNotFoundError(str(message_id))
    if message.role != Role.USER.value:
        raise MessageNotFoundError(str(message_id))

    if await attempts.has_completed_for_user_message(message_id):
        raise GenerationAlreadyCompletedError("That message already has a completed response.")

    active = await attempts.get_active_for_conversation(conversation_id)
    if active is not None:
        raise GenerationInProgressError(active.id)

    try:
        attempt = await attempts.create(
            conversation_id=conversation_id,
            user_message_id=message_id,
            provider=provider_name,
            model=model,
        )
        await conversations.touch(conversation_id)
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        active = await attempts.get_active_for_conversation(conversation_id)
        if active is not None:
            raise GenerationInProgressError(active.id) from error
        raise

    return PreparedGeneration(
        conversation_id=conversation_id,
        conversation_title=conversation.title,
        user_message_id=message_id,
        attempt_id=attempt.id,
        is_new_conversation=False,
    )


async def stream_generation(
    prepared: PreparedGeneration,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    provider: ChatProvider,
    system_prompt: str,
    model: str,
    max_output_tokens: int,
    registry: GenerationRegistry,
) -> AsyncGenerator[GenerationEvent, None]:
    """Yield the application stream events for one generation."""
    active = await registry.register(prepared.attempt_id)
    buffer: list[str] = []
    usage: Usage | None = None
    finish_reason = "stop"
    stopped = False
    finalized = False

    try:
        yield (
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

        async with session_factory() as session:
            history = await MessageRepository(session).list_for_conversation(
                prepared.conversation_id
            )
        request = GenerationRequest(
            model=model,
            system_prompt=system_prompt,
            messages=[
                ProviderMessage(role=Role(message.role), content=message.content)
                for message in history
            ],
            max_output_tokens=max_output_tokens,
            request_id=str(prepared.attempt_id),
        )

        try:
            async for event in provider.stream(request):
                if active.stop_requested.is_set():
                    stopped = True
                    break
                if isinstance(event, TextDelta):
                    buffer.append(event.text)
                    yield "delta", {"text": event.text}
                else:
                    usage = event.usage
                    finish_reason = event.finish_reason
        except ProviderError as error:
            finalized = True
            finalized_turn = await _finalize(
                session_factory,
                prepared=prepared,
                status=AttemptStatus.FAILED,
                text="".join(buffer),
                usage=usage,
                error_code=error.code,
                error_message=str(error),
            )
            yield (
                "error",
                {
                    "code": error.code,
                    "message": str(error),
                    "retryable": error.retryable,
                    "attempt_id": str(prepared.attempt_id),
                    "assistant_message_id": _optional_id(finalized_turn.assistant_message_id),
                },
            )
            return

        if active.stop_requested.is_set():
            stopped = True

        status = AttemptStatus.INTERRUPTED if stopped else AttemptStatus.COMPLETED
        finalized = True
        finalized_turn = await _finalize(
            session_factory,
            prepared=prepared,
            status=status,
            text="".join(buffer),
            usage=usage,
            error_code="stopped_by_user" if stopped else None,
        )

        if usage is not None:
            yield (
                "usage",
                {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "thought_tokens": usage.thought_tokens,
                    "total_tokens": usage.total_tokens,
                },
            )

        yield (
            "done",
            {
                "attempt_id": str(prepared.attempt_id),
                "status": status.value,
                "assistant_message_id": _optional_id(finalized_turn.assistant_message_id),
                "finish_reason": "interrupted" if stopped else finish_reason,
            },
        )
    except (asyncio.CancelledError, GeneratorExit):
        # Client disconnect, refresh, or the stop grace timer. The attempt must
        # still become interrupted, so the write is protected from cancellation.
        # A disconnect after the terminal write must not overwrite a completed
        # attempt, hence the guard.
        if not finalized:
            await _finalize_after_cancel(
                session_factory,
                prepared=prepared,
                text="".join(buffer),
                usage=usage,
            )
        raise
    finally:
        await registry.deregister(prepared.attempt_id)


async def _finalize(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    prepared: PreparedGeneration,
    status: AttemptStatus,
    text: str,
    usage: Usage | None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> FinalizedTurn:
    """Write the terminal state in one transaction."""
    async with session_factory() as session:
        messages = MessageRepository(session)
        attempts = AttemptRepository(session)

        assistant_message_id: uuid.UUID | None = None
        if text:
            assistant = await messages.append(
                conversation_id=prepared.conversation_id,
                role=Role.ASSISTANT,
                content=text,
            )
            assistant_message_id = assistant.id
            await ConversationRepository(session).touch(prepared.conversation_id)

        await attempts.finalize(
            prepared.attempt_id,
            status=status,
            assistant_message_id=assistant_message_id,
            error_code=error_code,
            error_message=error_message,
            usage=_usage_raw(usage),
            input_tokens=usage.input_tokens if usage is not None else None,
            output_tokens=usage.output_tokens if usage is not None else None,
            thought_tokens=usage.thought_tokens if usage is not None else None,
            total_tokens=usage.total_tokens if usage is not None else None,
        )
        await session.commit()

    return FinalizedTurn(
        status=status,
        assistant_message_id=assistant_message_id,
        content=text,
    )


async def _finalize_after_cancel(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    prepared: PreparedGeneration,
    text: str,
    usage: Usage | None,
) -> None:
    """Finalize an interrupted attempt while the current task is cancelled."""
    task = asyncio.create_task(
        _finalize(
            session_factory,
            prepared=prepared,
            status=AttemptStatus.INTERRUPTED,
            text=text,
            usage=usage,
            error_code="interrupted",
        )
    )
    with suppress(asyncio.CancelledError):
        await asyncio.shield(task)
    if not task.done():  # pragma: no cover - only if cancelled twice
        task.add_done_callback(lambda _: None)


def _usage_raw(usage: Usage | None) -> dict[str, Any] | None:
    if usage is None or usage.raw is None:
        return None
    return dict(usage.raw)


def _optional_id(value: uuid.UUID | None) -> str | None:
    return str(value) if value is not None else None
