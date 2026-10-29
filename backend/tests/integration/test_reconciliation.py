"""Startup reconciliation of attempts stranded by a crash."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lucid.domain.enums import AttemptStatus, Role
from lucid.domain.outcome import AttemptOutcome
from lucid.persistence.reconciliation import reconcile_stale_attempts
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)
from lucid.persistence.tables import GenerationAttempt


async def _seed(
    session: AsyncSession,
    *,
    status: AttemptStatus,
) -> GenerationAttempt:
    conversation = await ConversationRepository(session).create(first_message="orphan")
    user_message = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.USER, content="orphan"
    )
    attempt = await AttemptRepository(session).create(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        provider="fake",
        model="fake-model",
    )
    if status is not AttemptStatus.IN_PROGRESS:
        await AttemptRepository(session).finalize(attempt.id, AttemptOutcome(status=status))
    await session.commit()
    return attempt


async def test_marks_in_progress_attempts_interrupted(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    attempt = await _seed(session, status=AttemptStatus.IN_PROGRESS)

    repaired = await reconcile_stale_attempts(session_factory)

    assert repaired == 1
    async with session_factory() as verify:
        stored = await verify.get(GenerationAttempt, attempt.id)
    assert stored is not None
    assert stored.status == AttemptStatus.INTERRUPTED.value
    assert stored.error_code == "process_restart"
    assert stored.completed_at is not None
    assert stored.completed_at <= datetime.now(UTC)


async def test_leaves_terminal_attempts_alone(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    completed = await _seed(session, status=AttemptStatus.COMPLETED)
    failed = await _seed(session, status=AttemptStatus.FAILED)

    repaired = await reconcile_stale_attempts(session_factory)

    assert repaired == 0
    async with session_factory() as verify:
        first = await verify.get(GenerationAttempt, completed.id)
        second = await verify.get(GenerationAttempt, failed.id)
    assert first is not None and first.status == AttemptStatus.COMPLETED.value
    assert second is not None and second.status == AttemptStatus.FAILED.value
    assert second.error_code is None


async def test_is_idempotent(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session, status=AttemptStatus.IN_PROGRESS)

    assert await reconcile_stale_attempts(session_factory) == 1
    assert await reconcile_stale_attempts(session_factory) == 0
