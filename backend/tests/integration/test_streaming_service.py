"""Streaming service behaviour: incremental delivery, stop, disconnect."""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import suppress

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.application.chat_service import (
    GenerationEvent,
    PreparedGeneration,
    prepare_message,
    stream_generation,
)
from lucid.application.registry import GenerationRegistry
from lucid.application.retry import RetryPolicy
from lucid.domain.enums import AttemptStatus
from lucid.domain.errors import ProviderUnavailable
from lucid.persistence.tables import GenerationAttempt
from lucid.providers.fake import FakeProvider, FakeScript

TERMINAL = {"done", "error"}


async def _prepare(session: AsyncSession, text: str, provider: FakeProvider) -> PreparedGeneration:
    return await prepare_message(
        session,
        content=text,
        conversation_id=None,
        provider_name=provider.name,
        model="fake-model",
    )


def _stream(
    prepared: PreparedGeneration,
    provider: FakeProvider,
    session_factory: async_sessionmaker[AsyncSession],
    registry: GenerationRegistry,
    *,
    first_token_timeout: float | None = None,
    policy: RetryPolicy | None = None,
) -> AsyncGenerator[GenerationEvent, None]:
    return stream_generation(
        prepared,
        session_factory=session_factory,
        provider=provider,
        system_prompt="test",
        model="fake-model",
        max_output_tokens=64,
        registry=registry,
        retry_policy=policy,
        first_token_timeout=first_token_timeout,
    )


async def _drain(events: AsyncGenerator[GenerationEvent, None]) -> list[GenerationEvent]:
    return [event async for event in events]


async def _attempt(
    session_factory: async_sessionmaker[AsyncSession], attempt_id: uuid.UUID
) -> GenerationAttempt:
    async with session_factory() as session:
        attempt = await session.get(GenerationAttempt, attempt_id)
        assert attempt is not None
        return attempt


async def test_events_arrive_incrementally(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(FakeScript(deltas=("a", "b", "c"), delay_seconds=0.01))
    registry = GenerationRegistry()
    prepared = await _prepare(session, "stream please", provider)

    events = _stream(prepared, provider, session_factory, registry)

    first = await anext(events)
    second = await anext(events)

    assert first[0] == "meta"
    assert second == ("delta", {"text": "a"})

    remaining = await _drain(events)
    assert [name for name, _ in remaining] == ["delta", "delta", "usage", "done"]


async def test_success_persists_one_assistant_message_and_one_terminal_event(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(FakeScript(deltas=("Hello", " there")))
    registry = GenerationRegistry()
    prepared = await _prepare(session, "hi", provider)

    events = await _drain(_stream(prepared, provider, session_factory, registry))

    names = [name for name, _ in events]
    assert names.count("done") == 1
    assert not set(names) & (TERMINAL - {"done"})
    assert names[0] == "meta"
    assert names[-1] == "done"

    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.COMPLETED.value
    assert attempt.assistant_message_id is not None
    assert attempt.total_tokens == 18


async def test_stop_finalizes_as_interrupted_and_keeps_partial_text(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(
        FakeScript(deltas=("partial ", "text ", "that ", "keeps ", "going"), delay_seconds=0.01)
    )
    registry = GenerationRegistry()
    prepared = await _prepare(session, "stop me", provider)

    events = _stream(prepared, provider, session_factory, registry)
    await anext(events)  # meta
    await anext(events)  # first delta
    assert await registry.request_stop(prepared.attempt_id) is True

    remaining = await _drain(events)
    names = [name for name, _ in remaining]
    assert names[-1] == "done"
    assert names.count("done") == 1

    done = remaining[-1][1]
    assert done["status"] == "interrupted"
    assert done["finish_reason"] == "interrupted"

    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.INTERRUPTED.value
    assert attempt.error_code == "stopped_by_user"
    assert attempt.assistant_message_id is not None


async def test_stop_before_first_token_leaves_no_assistant_message(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(FakeScript(deltas=("slow",), delay_seconds=0.01))
    registry = GenerationRegistry()
    prepared = await _prepare(session, "stop early", provider)

    events = _stream(prepared, provider, session_factory, registry)
    await anext(events)  # meta
    await registry.request_stop(prepared.attempt_id)
    remaining = await _drain(events)

    assert remaining[-1][1]["status"] == "interrupted"
    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.INTERRUPTED.value
    assert attempt.assistant_message_id is None


async def test_client_close_finalizes_as_interrupted(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(
        FakeScript(deltas=("one ", "two ", "three ", "four"), delay_seconds=0.01)
    )
    registry = GenerationRegistry()
    prepared = await _prepare(session, "close early", provider)

    events = _stream(prepared, provider, session_factory, registry)
    await anext(events)  # meta
    await anext(events)  # first delta
    await events.aclose()  # what Starlette does when the client goes away

    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.INTERRUPTED.value
    assert attempt.assistant_message_id is not None
    assert await registry.is_active(prepared.attempt_id) is False


async def test_cancelled_task_still_persists_the_interruption(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(
        FakeScript(deltas=("a ", "b ", "c ", "d ", "e ", "f"), delay_seconds=0.02)
    )
    registry = GenerationRegistry()
    prepared = await _prepare(session, "cancel me", provider)
    events = _stream(prepared, provider, session_factory, registry)

    async def consume() -> None:
        async for _ in events:
            pass

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.06)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.INTERRUPTED.value
    assert attempt.assistant_message_id is not None


async def test_provider_failure_after_partial_text_keeps_the_message(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(
        FakeScript(
            deltas=("partial ", "then boom"),
            fail_after_first_token=ProviderUnavailable(detail="upstream 503"),
        )
    )
    registry = GenerationRegistry()
    prepared = await _prepare(session, "fail late", provider)

    events = await _drain(_stream(prepared, provider, session_factory, registry))

    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert names.count("error") == 1
    assert "done" not in names

    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.FAILED.value
    assert attempt.error_code == "provider_unavailable"
    assert attempt.assistant_message_id is not None


async def test_empty_completion_is_a_visible_retryable_failure(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Regression: an empty completion used to look like a silent success."""
    provider = FakeProvider(FakeScript(deltas=(), usage=None))
    registry = GenerationRegistry()
    prepared = await _prepare(session, "say nothing", provider)

    events = await _drain(_stream(prepared, provider, session_factory, registry))

    names = [name for name, _ in events]
    assert names == ["meta", "error"]
    error = events[-1][1]
    assert error["code"] == "empty_response"
    assert error["retryable"] is True

    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.FAILED.value
    assert attempt.error_code == "empty_response"
    assert attempt.assistant_message_id is None


async def test_queued_provider_fails_fast_at_the_first_token_deadline(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Regression: a queued request waited blank for 30-60 seconds."""
    provider = FakeProvider(FakeScript(deltas=("late",), delay_seconds=0.25))
    registry = GenerationRegistry()
    prepared = await _prepare(session, "wait for it", provider)
    policy = RetryPolicy(max_retries=0, base_delay_ms=1, jitter=False)

    events = await _drain(
        _stream(
            prepared,
            provider,
            session_factory,
            registry,
            first_token_timeout=0.05,
            policy=policy,
        )
    )

    names = [name for name, _ in events]
    assert names == ["meta", "error"]
    error = events[-1][1]
    assert error["code"] == "provider_timeout"
    assert error["retryable"] is True

    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.FAILED.value
    assert attempt.error_code == "provider_timeout"


async def test_first_token_timeout_is_not_automatically_retried(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A queued provider should fail once, not three times over 75 seconds."""
    provider = FakeProvider(FakeScript(deltas=("late",), delay_seconds=0.3))
    registry = GenerationRegistry()
    prepared = await _prepare(session, "still queued", provider)

    events = await _drain(
        _stream(
            prepared,
            provider,
            session_factory,
            registry,
            first_token_timeout=0.05,
            policy=RetryPolicy(max_retries=2, base_delay_ms=1, jitter=False),
        )
    )

    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "provider_timeout"
    assert len(provider.requests) == 1


async def test_first_token_deadline_does_not_fire_after_text_arrives(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(FakeScript(deltas=("a", "b", "c"), delay_seconds=0.02))
    registry = GenerationRegistry()
    prepared = await _prepare(session, "steady", provider)

    events = await _drain(
        _stream(
            prepared,
            provider,
            session_factory,
            registry,
            first_token_timeout=0.5,
        )
    )

    assert [name for name, _ in events][-1] == "done"
    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.COMPLETED.value


async def test_registry_is_empty_after_each_stream(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider()
    registry = GenerationRegistry()
    prepared = await _prepare(session, "cleanup", provider)

    await _drain(_stream(prepared, provider, session_factory, registry))

    assert registry.size == 0


async def test_attempt_rows_stay_unique_per_message(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider()
    registry = GenerationRegistry()
    prepared = await _prepare(session, "one turn", provider)

    await _drain(_stream(prepared, provider, session_factory, registry))

    async with session_factory() as verify:
        rows = (
            (
                await verify.execute(
                    select(GenerationAttempt).where(
                        GenerationAttempt.user_message_id == prepared.user_message_id
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(rows) == 1
    assert rows[0].attempt_no == 1
