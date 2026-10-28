"""Database-level invariants: constraints, cascades, and nulling behaviour."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from chatbot.domain.enums import AttemptStatus, Role
from chatbot.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)
from chatbot.persistence.tables import Conversation, GenerationAttempt, Message


async def _seed(session: AsyncSession) -> tuple[Conversation, Message, GenerationAttempt]:
    conversation = await ConversationRepository(session).create(first_message="hello there")
    user_message = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.USER, content="hello there"
    )
    attempt = await AttemptRepository(session).create(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        provider="fake",
        model="fake-model",
    )
    await session.commit()
    return conversation, user_message, attempt


async def test_duplicate_message_sequence_is_rejected(session: AsyncSession) -> None:
    conversation, user_message, _ = await _seed(session)

    session.add(
        Message(
            conversation_id=conversation.id,
            role=Role.ASSISTANT.value,
            content="duplicate position",
            seq=user_message.seq,
        )
    )

    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_second_active_attempt_for_one_conversation_is_rejected(
    session: AsyncSession,
) -> None:
    conversation, user_message, _ = await _seed(session)

    session.add(
        GenerationAttempt(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            attempt_no=2,
            status=AttemptStatus.IN_PROGRESS.value,
            provider="fake",
            model="fake-model",
        )
    )

    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_active_attempts_are_independent_across_conversations(
    session: AsyncSession,
) -> None:
    first, _, _ = await _seed(session)
    second, _, _ = await _seed(session)

    assert first.id != second.id
    active = await AttemptRepository(session).get_active_for_conversation(second.id)
    assert active is not None


async def test_deleting_a_conversation_cascades_to_messages_and_attempts(
    session: AsyncSession,
) -> None:
    conversation, _, _ = await _seed(session)

    deleted = await ConversationRepository(session).delete(conversation.id)
    await session.commit()

    assert deleted
    message_count = await session.scalar(
        select(func.count()).select_from(Message).where(Message.conversation_id == conversation.id)
    )
    attempt_count = await session.scalar(
        select(func.count())
        .select_from(GenerationAttempt)
        .where(GenerationAttempt.conversation_id == conversation.id)
    )
    assert message_count == 0
    assert attempt_count == 0


async def test_deleting_the_assistant_message_keeps_the_attempt(
    session: AsyncSession,
) -> None:
    conversation, user_message, attempt = await _seed(session)
    assistant = await MessageRepository(session).append(
        conversation_id=conversation.id, role=Role.ASSISTANT, content="an answer"
    )
    await AttemptRepository(session).finalize(
        attempt.id,
        status=AttemptStatus.COMPLETED,
        assistant_message_id=assistant.id,
    )
    await session.commit()

    await session.delete(assistant)
    await session.commit()

    survivor = await session.get(GenerationAttempt, attempt.id)
    assert survivor is not None
    await session.refresh(survivor)
    assert survivor.assistant_message_id is None
    assert survivor.user_message_id == user_message.id


async def test_title_length_is_enforced_by_the_database(session: AsyncSession) -> None:
    session.add(Conversation(title="x" * 81))

    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_empty_title_is_rejected(session: AsyncSession) -> None:
    session.add(Conversation(title=""))

    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_empty_message_content_is_rejected(session: AsyncSession) -> None:
    conversation, user_message, _ = await _seed(session)

    session.add(
        Message(
            conversation_id=conversation.id,
            role=Role.ASSISTANT.value,
            content="",
            seq=user_message.seq + 1,
        )
    )

    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_unknown_role_is_rejected(session: AsyncSession) -> None:
    conversation, user_message, _ = await _seed(session)

    session.add(
        Message(
            conversation_id=conversation.id,
            role="system",
            content="not allowed",
            seq=user_message.seq + 1,
        )
    )

    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_usage_metadata_round_trips(session: AsyncSession) -> None:
    _, _, attempt = await _seed(session)

    await AttemptRepository(session).finalize(
        attempt.id,
        status=AttemptStatus.COMPLETED,
        usage={"total_input_tokens": 11, "total_output_tokens": 90},
        input_tokens=11,
        output_tokens=90,
        thought_tokens=0,
        total_tokens=101,
    )
    await session.commit()
    await session.refresh(attempt)

    stored = attempt
    assert stored.status == AttemptStatus.COMPLETED.value
    assert stored.usage_raw == {"total_input_tokens": 11, "total_output_tokens": 90}
    assert stored.completed_at is not None
    assert stored.completed_at.tzinfo is not None


async def test_finalize_without_usage_leaves_fields_null(session: AsyncSession) -> None:
    _, _, attempt = await _seed(session)

    await AttemptRepository(session).finalize(attempt.id, status=AttemptStatus.INTERRUPTED)
    await session.commit()
    await session.refresh(attempt)

    stored = attempt
    assert stored.input_tokens is None
    assert stored.usage_raw is None
    assert stored.status == AttemptStatus.INTERRUPTED.value


async def test_conversation_ids_are_time_ordered(session: AsyncSession) -> None:
    first, _, _ = await _seed(session)
    second, _, _ = await _seed(session)

    assert first.id.int < second.id.int
    assert first.created_at <= datetime.now(UTC)


async def test_unknown_conversation_returns_none(session: AsyncSession) -> None:
    assert await ConversationRepository(session).get(uuid.uuid4()) is None
    assert await ConversationRepository(session).delete(uuid.uuid4()) is False
