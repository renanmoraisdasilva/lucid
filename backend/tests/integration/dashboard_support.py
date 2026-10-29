"""Seed helpers for dashboard integration tests."""

from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from lucid.domain.enums import AttemptStatus, Role
from lucid.domain.outcome import AttemptOutcome
from lucid.persistence.repositories import (
    AttemptRepository,
    ConversationRepository,
    MessageRepository,
)
from lucid.persistence.tables import Conversation, GenerationAttempt, Message


async def seed_conversation(session: AsyncSession, title: str) -> tuple[Conversation, Message]:
    conversation = await ConversationRepository(session).create(first_message=title)
    user = await MessageRepository(session).append(
        conversation_id=conversation.id,
        role=Role.USER,
        content=title,
    )
    await session.commit()
    return conversation, user


async def seed_attempt(
    session: AsyncSession,
    conversation: Conversation,
    user: Message,
    *,
    started_at: datetime,
    status: AttemptStatus | None,
    first_token_at: datetime | None = None,
    completed_at: datetime | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    context_tokens: int | None = None,
    http_status: int | None = None,
    retry_count: int = 0,
    error_code: str | None = None,
    with_assistant: bool = False,
) -> GenerationAttempt:
    attempt = await AttemptRepository(session).create(
        conversation_id=conversation.id,
        user_message_id=user.id,
        provider="fake",
        model="fake-model",
    )
    assistant_id = None
    if with_assistant:
        assistant = await MessageRepository(session).append(
            conversation_id=conversation.id,
            role=Role.ASSISTANT,
            content="answer",
        )
        assistant_id = assistant.id
    await session.execute(
        update(GenerationAttempt)
        .where(GenerationAttempt.id == attempt.id)
        .values(started_at=started_at)
    )
    if status is not None:
        await AttemptRepository(session).finalize(
            attempt.id,
            AttemptOutcome(
                status=status,
                assistant_message_id=assistant_id,
                error_code=error_code,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                first_token_at=first_token_at,
                http_status=http_status,
                retry_count=retry_count,
                context_tokens=context_tokens,
            ),
        )
    if completed_at is not None:
        await session.execute(
            update(GenerationAttempt)
            .where(GenerationAttempt.id == attempt.id)
            .values(completed_at=completed_at)
        )
    await session.commit()
    return attempt
