"""Telemetry retention removes old attempts but keeps conversation history."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.application.dashboard import retention
from lucid.application.dashboard.retention import delete_expired_attempts
from lucid.domain.enums import AttemptStatus, Role
from lucid.domain.outcome import AttemptOutcome
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)
from lucid.persistence.tables import Conversation, GenerationAttempt, Message

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
CUTOFF = NOW - timedelta(days=30)


async def _seed(
    session: AsyncSession,
    *,
    started_at: datetime,
    status: AttemptStatus | None,
    with_assistant: bool = False,
) -> tuple[Conversation, GenerationAttempt, Message | None]:
    conversations = ConversationRepository(session)
    messages = MessageRepository(session)
    attempts = AttemptRepository(session)

    conversation = await conversations.create(first_message="retention")
    user_message = await messages.append(
        conversation_id=conversation.id,
        role=Role.USER,
        content="keep my history",
    )
    attempt = await attempts.create(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        provider="fake",
        model="fake-model",
    )
    await session.execute(
        update(GenerationAttempt)
        .where(GenerationAttempt.id == attempt.id)
        .values(started_at=started_at)
    )

    assistant = None
    if with_assistant:
        assistant = await messages.append(
            conversation_id=conversation.id,
            role=Role.ASSISTANT,
            content="the answer stays",
        )
    if status is not None:
        await attempts.finalize(
            attempt.id,
            AttemptOutcome(
                status=status,
                assistant_message_id=assistant.id if assistant is not None else None,
            ),
        )
    await session.commit()
    return conversation, attempt, assistant


async def test_deletes_only_old_terminal_attempts(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    old_conversation, old_attempt, old_assistant = await _seed(
        session,
        started_at=NOW - timedelta(days=31),
        status=AttemptStatus.COMPLETED,
        with_assistant=True,
    )
    _, boundary_attempt, _ = await _seed(session, started_at=CUTOFF, status=AttemptStatus.FAILED)
    _, recent_attempt, _ = await _seed(
        session, started_at=NOW - timedelta(days=1), status=AttemptStatus.INTERRUPTED
    )
    _, active_attempt, _ = await _seed(session, started_at=NOW - timedelta(days=60), status=None)

    deleted = await delete_expired_attempts(session_factory, retention_days=30, now=NOW)

    assert deleted == 1
    async with session_factory() as check:
        assert await check.get(GenerationAttempt, old_attempt.id) is None
        assert await check.get(GenerationAttempt, boundary_attempt.id) is not None
        assert await check.get(GenerationAttempt, recent_attempt.id) is not None
        assert await check.get(GenerationAttempt, active_attempt.id) is not None

        # The attempt is telemetry; the conversation and its messages are history.
        assert await check.get(Conversation, old_conversation.id) is not None
        assert old_assistant is not None
        assert await check.get(Message, old_assistant.id) is not None


async def test_returns_zero_when_nothing_expired(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session, started_at=NOW - timedelta(days=2), status=AttemptStatus.COMPLETED)

    assert await delete_expired_attempts(session_factory, retention_days=30, now=NOW) == 0


async def test_periodic_retention_can_be_cancelled(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    async def fake_delete(
        _factory: async_sessionmaker[AsyncSession], *, retention_days: int
    ) -> int:
        calls.append(retention_days)
        return 0

    monkeypatch.setattr(retention, "delete_expired_attempts", fake_delete)
    task = asyncio.create_task(
        retention.periodic_retention(
            session_factory,
            retention_days=30,
            interval_seconds=0,
        )
    )
    for _ in range(100):
        if len(calls) >= 2:
            break
        await asyncio.sleep(0)
    assert len(calls) >= 2

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert calls[:2] == [30, 30]
