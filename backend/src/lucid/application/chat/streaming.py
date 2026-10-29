"""Streaming chat orchestration.

The stream buffers text in memory, persists one terminal state, and emits at most
one terminal event. This module owns the flow; retries, finalization, telemetry
and payload construction live beside it.
"""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.application.chat.events import (
    GenerationEvent,
    done_event,
    error_event,
    meta_event,
    usage_event,
)
from lucid.application.chat.finalize import (
    TurnOutcome,
    finalize,
    finalize_after_cancel,
)
from lucid.application.chat.options import GenerationOptions
from lucid.application.chat.retries import RetryLoop, stream_with_retries
from lucid.application.chat.telemetry import AttemptTelemetry
from lucid.application.chat.turns import PreparedGeneration
from lucid.application.context import select_history
from lucid.application.registry import ActiveGeneration, GenerationRegistry
from lucid.domain.enums import AttemptStatus, Role
from lucid.domain.errors import EmptyProviderResponse, ProviderError, ProviderRateLimited
from lucid.domain.provider import (
    ChatProvider,
    GenerationRequest,
    ProviderMessage,
    TextDelta,
    Usage,
)
from lucid.persistence.repositories import MessageRepository

__all__ = ["GenerationEvent", "stream_generation"]


@dataclass(slots=True)
class _StreamState:
    """Mutable state for one attempt."""

    buffer: list[str] = field(default_factory=list[str])
    usage: Usage | None = None
    finish_reason: str = "stop"
    stopped: bool = False
    finalized: bool = False


@dataclass(frozen=True, slots=True)
class _RunContext:
    """The immutable inputs shared by the stream helpers."""

    prepared: PreparedGeneration
    session_factory: async_sessionmaker[AsyncSession]
    provider: ChatProvider
    active: ActiveGeneration
    options: GenerationOptions
    telemetry: AttemptTelemetry


async def stream_generation(
    prepared: PreparedGeneration,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    provider: ChatProvider,
    registry: GenerationRegistry,
    options: GenerationOptions,
) -> AsyncGenerator[GenerationEvent, None]:
    """Yield the application stream events for one generation."""
    state = _StreamState()
    telemetry = AttemptTelemetry()
    active = await registry.register(prepared.attempt_id)
    context = _RunContext(prepared, session_factory, provider, active, options, telemetry)

    try:
        yield meta_event(prepared, options.model)
        try:
            async for event in _run_generation(context, state):
                yield event
        except ProviderError as error:
            state.finalized = True
            yield await _failure_event(context, state, error)
            return

        state.finalized = True
        for event in await _completion_events(context, state):
            yield event
    except (asyncio.CancelledError, GeneratorExit):
        # Client disconnect, refresh, or the stop grace timer. The attempt must
        # still become interrupted, so the write is protected from cancellation.
        if not state.finalized:
            await finalize_after_cancel(
                session_factory,
                prepared,
                "".join(state.buffer),
                state.usage,
                telemetry,
            )
        raise
    finally:
        await registry.deregister(prepared.attempt_id)


async def _run_generation(
    context: _RunContext,
    state: _StreamState,
) -> AsyncGenerator[GenerationEvent, None]:
    """Open the provider stream and forward deltas until it ends or stops."""
    _raise_if_cooling_down(context.options)
    request = await _build_request(context)
    loop = RetryLoop(
        policy=context.options.retry_policy,
        stop_event=context.active.stop_requested,
        attempt_id=context.prepared.attempt_id,
        telemetry=context.telemetry,
        first_token_timeout=context.options.first_token_timeout,
    )

    async for event in stream_with_retries(context.provider, request, loop):
        if context.active.stop_requested.is_set():
            state.stopped = True
            break
        if isinstance(event, TextDelta):
            context.telemetry.mark_first_token()
            state.buffer.append(event.text)
            yield "delta", {"text": event.text}
        else:
            state.usage = event.usage
            state.finish_reason = event.finish_reason

    # A stop during the retry backoff yields no events, so re-check it here.
    if context.active.stop_requested.is_set():
        state.stopped = True

    # A finished stream with no text is a failure the user must see, not a
    # silent empty answer. A stopped turn is not an empty answer.
    if not state.buffer and not state.stopped:
        raise EmptyProviderResponse()


async def _build_request(context: _RunContext) -> GenerationRequest:
    async with context.session_factory() as session:
        history = await MessageRepository(session).list_for_conversation(
            context.prepared.conversation_id
        )
    options = context.options
    selection = select_history(
        [ProviderMessage(role=Role(message.role), content=message.content) for message in history],
        system_prompt=options.system_prompt,
        budget=options.context_budget,
    )
    context.telemetry.context_tokens = selection.estimated_tokens
    return GenerationRequest(
        model=options.model,
        system_prompt=options.system_prompt,
        messages=selection.messages,
        max_output_tokens=options.max_output_tokens,
        request_id=str(context.prepared.attempt_id),
    )


async def _failure_event(
    context: _RunContext,
    state: _StreamState,
    error: ProviderError,
) -> GenerationEvent:
    cooldown = context.options.cooldown
    if isinstance(error, ProviderRateLimited) and cooldown is not None:
        cooldown.record(error.retry_after_seconds)
    if error.http_status is not None:
        context.telemetry.http_status = error.http_status
    elif context.telemetry.first_token_at is not None:
        # A mid-stream failure still had a successful HTTP response.
        context.telemetry.http_status = 200

    turn = await finalize(
        context.session_factory,
        context.prepared,
        TurnOutcome(
            status=AttemptStatus.FAILED,
            text="".join(state.buffer),
            usage=state.usage,
            error_code=error.code,
            error_message=str(error),
            telemetry=context.telemetry,
        ),
    )
    return error_event(context.prepared, error, turn.assistant_message_id)


async def _completion_events(
    context: _RunContext,
    state: _StreamState,
) -> list[GenerationEvent]:
    status = AttemptStatus.INTERRUPTED if state.stopped else AttemptStatus.COMPLETED
    if status is AttemptStatus.COMPLETED or context.telemetry.first_token_at is not None:
        context.telemetry.http_status = 200
    turn = await finalize(
        context.session_factory,
        context.prepared,
        TurnOutcome(
            status=status,
            text="".join(state.buffer),
            usage=state.usage,
            error_code="stopped_by_user" if state.stopped else None,
            telemetry=context.telemetry,
        ),
    )

    events: list[GenerationEvent] = []
    if state.usage is not None:
        events.append(usage_event(state.usage))
    events.append(
        done_event(
            context.prepared,
            status,
            turn.assistant_message_id,
            "interrupted" if state.stopped else state.finish_reason,
        )
    )
    return events


def _raise_if_cooling_down(options: GenerationOptions) -> None:
    cooldown = options.cooldown
    if cooldown is None:
        return
    remaining = cooldown.remaining()
    if remaining > 0:
        raise ProviderRateLimited(
            cooldown.reason,
            retry_after_seconds=remaining,
            http_status=429,
        )
