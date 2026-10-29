"""Database-level invariants: constraints, cascades, and nulling behaviour."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from lucid.domain.enums import AttemptStatus, Role
from lucid.domain.outcome import AttemptOutcome
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)
from lucid.persistence.tables import Conversation, GenerationAttempt, Message


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
        AttemptOutcome(
            status=AttemptStatus.COMPLETED,
            assistant_message_id=assistant.id,
        ),
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
        AttemptOutcome(
            status=AttemptStatus.COMPLETED,
            usage_raw={"total_input_tokens": 11, "total_output_tokens": 90},
            input_tokens=11,
            output_tokens=90,
            thought_tokens=0,
            total_tokens=101,
        ),
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

    await AttemptRepository(session).finalize(
        attempt.id, AttemptOutcome(status=AttemptStatus.INTERRUPTED)
    )
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


def _assert_telemetry_schema(connection: Connection) -> None:
    inspector = inspect(connection)
    columns = {column["name"]: column for column in inspector.get_columns("generation_attempts")}
    assert {"first_token_at", "http_status", "retry_count", "context_tokens"} <= set(columns)
    assert columns["first_token_at"]["nullable"] is True
    assert columns["http_status"]["nullable"] is True
    assert columns["context_tokens"]["nullable"] is True
    assert columns["retry_count"]["nullable"] is False

    attempt_indexes = {
        index["name"] for index in inspector.get_indexes("generation_attempts") if index["name"]
    }
    message_indexes = {
        index["name"] for index in inspector.get_indexes("messages") if index["name"]
    }
    assert "ix_attempts_started_at" in attempt_indexes
    assert "ix_messages_created_at" in message_indexes

    checks = {
        check["name"]
        for check in inspector.get_check_constraints("generation_attempts")
        if check["name"]
    }
    assert {
        "ck_attempts_http_status",
        "ck_attempts_retry_count",
        "ck_attempts_context_tokens",
        "ck_attempts_first_token_after_start",
    } <= checks


async def test_dashboard_telemetry_schema(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.run_sync(_assert_telemetry_schema)
