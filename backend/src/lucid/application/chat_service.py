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
import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.application.context import ContextBudget, select_history
from lucid.application.cooldown import RateLimitCooldown
from lucid.application.registry import GenerationRegistry
from lucid.application.retry import RetryPolicy
from lucid.domain.enums import AttemptStatus, Role
from lucid.domain.errors import (
    EmptyProviderResponse,
    FirstTokenTimeout,
    ProviderError,
    ProviderRateLimited,
)
from lucid.domain.provider import (
    ChatProvider,
    GenerationRequest,
    ProviderEvent,
    ProviderMessage,
    StreamCompleted,
    TextDelta,
    Usage,
)
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)

logger = logging.getLogger(__name__)

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
    context_budget: ContextBudget | None = None,
    retry_policy: RetryPolicy | None = None,
    first_token_timeout: float | None = None,
    cooldown: RateLimitCooldown | None = None,
) -> AsyncGenerator[GenerationEvent, None]:
    """Yield the application stream events for one generation."""
    budget = context_budget or ContextBudget()
    policy = retry_policy or RetryPolicy()
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

        try:
            # Respect the provider's cool-down instead of calling into a 429 again.
            if cooldown is not None:
                remaining = cooldown.remaining()
                if remaining > 0:
                    raise ProviderRateLimited(retry_after_seconds=remaining)

            async with session_factory() as session:
                history = await MessageRepository(session).list_for_conversation(
                    prepared.conversation_id
                )
            request = GenerationRequest(
                model=model,
                system_prompt=system_prompt,
                messages=select_history(
                    [
                        ProviderMessage(role=Role(message.role), content=message.content)
                        for message in history
                    ],
                    system_prompt=system_prompt,
                    budget=budget,
                ),
                max_output_tokens=max_output_tokens,
                request_id=str(prepared.attempt_id),
            )

            async for event in _stream_with_retries(
                provider,
                request,
                policy=policy,
                stop_event=active.stop_requested,
                attempt_id=prepared.attempt_id,
                first_token_timeout=first_token_timeout,
            ):
                if active.stop_requested.is_set():
                    stopped = True
                    break
                if isinstance(event, TextDelta):
                    buffer.append(event.text)
                    yield "delta", {"text": event.text}
                else:
                    usage = event.usage
                    finish_reason = event.finish_reason

            # A stop during the retry backoff yields no events, so re-check it here.
            if active.stop_requested.is_set():
                stopped = True

            # A finished stream with no text is a failure the user must see, not a
            # silent empty answer. A stopped turn is not an empty answer.
            if not buffer and not stopped:
                raise EmptyProviderResponse()
        except ProviderError as error:
            if isinstance(error, ProviderRateLimited) and cooldown is not None:
                cooldown.record(error.retry_after_seconds)
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
                    "retry_after_seconds": error.retry_after_seconds,
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


async def _stream_with_retries(
    provider: ChatProvider,
    request: GenerationRequest,
    *,
    policy: RetryPolicy,
    stop_event: asyncio.Event,
    attempt_id: uuid.UUID,
    first_token_timeout: float | None = None,
) -> AsyncGenerator[ProviderEvent, None]:
    """Stream from the provider, retrying transient failures before any output.

    A retry re-issues the same request inside the same attempt; nothing is
    duplicated because retries are only allowed while the buffer is empty. Each
    attempt is bounded by ``first_token_timeout`` until the first text arrives,
    so a queued provider fails with a retryable timeout instead of a blank wait.
    """
    retry_index = 0
    emitted = False

    while True:
        try:
            async for event in _bounded_stream(
                provider,
                request,
                deadline=None if emitted else first_token_timeout,
            ):
                if isinstance(event, TextDelta):
                    emitted = True
                yield event
                if isinstance(event, StreamCompleted):
                    # The provider may keep its stream open after the terminal
                    # event; stop here instead of waiting for it to end.
                    return
            return
        except FirstTokenTimeout:
            # Never auto-retried: the provider is queued, so retrying only
            # multiplies the wait. The user still gets a retry action.
            raise
        except ProviderError as error:
            if isinstance(error, ProviderRateLimited) and (error.retry_after_seconds or 0) > 2.0:
                # A hint of several seconds means retrying now would only extend
                # the limit; surface it to the user instead.
                raise
            if not policy.is_retryable(error, has_output=emitted):
                raise
            if retry_index >= policy.max_retries:
                raise

            delay = policy.delay_seconds(retry_index)
            logger.warning(
                "retrying provider call",
                extra={
                    "ctx_attempt_id": str(attempt_id),
                    "ctx_retry_index": retry_index + 1,
                    "ctx_delay_seconds": round(delay, 3),
                    "ctx_error_code": error.code,
                },
            )
            retry_index += 1
            if await _sleep_or_stop(stop_event, delay):
                return


class _EndOfStream:
    """Queue sentinel marking a normally finished provider stream."""


_END_OF_STREAM = _EndOfStream()


async def _bounded_stream(
    provider: ChatProvider,
    request: GenerationRequest,
    *,
    deadline: float | None,
) -> AsyncGenerator[ProviderEvent, None]:
    """Yield provider events, enforcing a hard deadline on the first event.

    The provider runs in its own task so the deadline holds even when the SDK
    ignores cancellation while retrying internally. That was observed as a
    seven-minute wait that outlived ``asyncio.timeout``.
    """
    queue: asyncio.Queue[ProviderEvent | BaseException | _EndOfStream] = asyncio.Queue()
    producer = asyncio.create_task(_pump_stream(provider, request, queue))
    emitted = False

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=None if emitted else deadline)
            except TimeoutError as error:
                raise FirstTokenTimeout(detail=f"no provider event within {deadline}s") from error

            if isinstance(item, _EndOfStream):
                return
            if isinstance(item, BaseException):
                raise item
            emitted = True
            yield item
    finally:
        if not producer.done():
            # Do not await: a stuck SDK call must not block the response.
            producer.cancel()
            producer.add_done_callback(_discard_task_result)


async def _pump_stream(
    provider: ChatProvider,
    request: GenerationRequest,
    queue: asyncio.Queue[ProviderEvent | BaseException | _EndOfStream],
) -> None:
    """Forward provider events into a queue so the consumer can time out."""
    try:
        async for event in provider.stream(request):
            queue.put_nowait(event)
        queue.put_nowait(_END_OF_STREAM)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        queue.put_nowait(error)


def _discard_task_result(task: asyncio.Task[object]) -> None:
    with suppress(asyncio.CancelledError, Exception):
        task.exception()


async def _sleep_or_stop(stop_event: asyncio.Event, delay: float) -> bool:
    """Sleep unless a stop is requested first. Returns True when stopped."""
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=delay)
    except TimeoutError:
        return False
    return True


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
