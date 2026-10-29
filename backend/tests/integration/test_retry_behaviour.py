"""Retry behaviour inside a single generation attempt."""

import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.application.chat import (
    GenerationEvent,
    GenerationOptions,
    PreparedGeneration,
    prepare_message,
    stream_generation,
)
from lucid.application.context import ContextBudget
from lucid.application.registry import GenerationRegistry
from lucid.application.retry import RetryPolicy
from lucid.domain.enums import AttemptStatus
from lucid.domain.errors import (
    ProviderInvalidRequest,
    ProviderRateLimited,
    ProviderUnavailable,
)
from lucid.persistence.tables import GenerationAttempt, Message
from lucid.providers.fake import FakeProvider, FakeScript

FAST_POLICY = RetryPolicy(max_retries=2, base_delay_ms=1, max_delay_ms=5, jitter=False)
ROOMY_BUDGET = ContextBudget(max_input_tokens=20_000, reserved_output_tokens=1_000)


async def _prepare(
    session: AsyncSession,
    provider: FakeProvider,
    *,
    content: str = "hello",
) -> PreparedGeneration:
    return await prepare_message(
        session,
        content=content,
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
    policy: RetryPolicy = FAST_POLICY,
    budget: ContextBudget = ROOMY_BUDGET,
) -> AsyncGenerator[GenerationEvent, None]:
    return stream_generation(
        prepared,
        session_factory=session_factory,
        provider=provider,
        registry=registry,
        options=GenerationOptions(
            system_prompt="test",
            model="fake-model",
            max_output_tokens=64,
            context_budget=budget,
            retry_policy=policy,
        ),
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


async def _message_count(
    session_factory: async_sessionmaker[AsyncSession], conversation_id: uuid.UUID
) -> int:
    async with session_factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Message)
                    .where(Message.conversation_id == conversation_id)
                )
            ).scalar_one()
        )


async def test_retries_transient_failures_then_succeeds(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(
        scripts=[
            FakeScript(fail_before_first_token=ProviderRateLimited()),
            FakeScript(fail_before_first_token=ProviderUnavailable()),
            FakeScript(deltas=("recovered",)),
        ]
    )
    registry = GenerationRegistry()
    prepared = await _prepare(session, provider)

    events = await _drain(_stream(prepared, provider, session_factory, registry))

    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert names[-1] == "done"
    assert [data["text"] for name, data in events if name == "delta"] == ["recovered"]
    assert len(provider.requests) == 3

    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.COMPLETED.value
    assert attempt.retry_count == 2
    assert attempt.http_status == 200
    assert attempt.first_token_at is not None
    assert await _message_count(session_factory, prepared.conversation_id) == 2


async def test_exhausted_retries_fail_the_attempt(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(
        scripts=[
            FakeScript(fail_before_first_token=ProviderRateLimited()),
            FakeScript(fail_before_first_token=ProviderRateLimited()),
            FakeScript(fail_before_first_token=ProviderRateLimited()),
        ]
    )
    registry = GenerationRegistry()
    prepared = await _prepare(session, provider)

    events = await _drain(_stream(prepared, provider, session_factory, registry))

    names = [name for name, _ in events]
    assert names == ["meta", "error"]
    assert len(provider.requests) == 3

    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.FAILED.value
    assert attempt.error_code == "provider_rate_limited"
    assert attempt.retry_count == 2
    assert attempt.http_status is None


async def test_does_not_retry_after_text_has_streamed(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(
        FakeScript(
            deltas=("partial ", "boom"),
            fail_after_first_token=ProviderUnavailable(),
        )
    )
    registry = GenerationRegistry()
    prepared = await _prepare(session, provider)

    events = await _drain(_stream(prepared, provider, session_factory, registry))

    assert len(provider.requests) == 1
    assert [name for name, _ in events][-1] == "error"
    assert await _message_count(session_factory, prepared.conversation_id) == 2


async def test_does_not_retry_permanent_failures(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(
        FakeScript(fail_before_first_token=ProviderInvalidRequest(detail="bad shape"))
    )
    registry = GenerationRegistry()
    prepared = await _prepare(session, provider)

    await _drain(_stream(prepared, provider, session_factory, registry))

    assert len(provider.requests) == 1


async def test_stop_interrupts_the_backoff_wait(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider(
        scripts=[
            FakeScript(fail_before_first_token=ProviderRateLimited()),
            FakeScript(deltas=("never",)),
        ]
    )
    registry = GenerationRegistry()
    prepared = await _prepare(session, provider)
    slow_policy = RetryPolicy(max_retries=2, base_delay_ms=5_000, jitter=False)
    events = _stream(prepared, provider, session_factory, registry, policy=slow_policy)

    await anext(events)  # meta
    await registry.request_stop(prepared.attempt_id)
    remaining = await _drain(events)

    assert remaining[-1][1]["status"] == "interrupted"
    assert len(provider.requests) == 1

    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.INTERRUPTED.value


async def test_context_too_large_fails_without_calling_the_provider(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider()
    registry = GenerationRegistry()
    prepared = await _prepare(session, provider, content="x" * 4_000)
    tiny_budget = ContextBudget(
        max_input_tokens=1_000,
        reserved_output_tokens=900,
        safety_margin_tokens=0,
    )

    events = await _drain(
        _stream(prepared, provider, session_factory, registry, budget=tiny_budget)
    )

    assert provider.requests == []
    error = events[-1][1]
    assert events[-1][0] == "error"
    assert error["code"] == "context_too_large"
    assert error["retryable"] is False

    attempt = await _attempt(session_factory, prepared.attempt_id)
    assert attempt.status == AttemptStatus.FAILED.value


async def test_context_selection_bounds_the_provider_request(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = FakeProvider()
    registry = GenerationRegistry()
    prepared = await _prepare(session, provider)
    narrow_budget = ContextBudget(
        max_input_tokens=2_000,
        reserved_output_tokens=1_000,
        safety_margin_tokens=0,
        max_messages=1,
    )

    await _drain(_stream(prepared, provider, session_factory, registry, budget=narrow_budget))

    assert provider.requests
    assert len(provider.requests[0].messages) == 1
    assert provider.requests[0].messages[-1].role.value == "user"
