"""Repository layer: the only place that issues queries for the chat domain."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from chatbot.application.cursor import Cursor
from chatbot.application.titles import derive_title
from chatbot.domain.enums import AttemptStatus, Role
from chatbot.persistence.tables import Conversation, GenerationAttempt, Message


@dataclass(frozen=True, slots=True)
class ConversationPage:
    """One page of conversations plus whether more rows exist."""

    items: Sequence[Conversation]
    has_more: bool


class ConversationRepository:
    """Conversation reads and writes. Callers own the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, first_message: str, title: str | None = None) -> Conversation:
        """Insert a conversation, deriving the title from its first message."""
        conversation = Conversation(title=title or derive_title(first_message))
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def get(self, conversation_id: uuid.UUID) -> Conversation | None:
        return await self._session.get(Conversation, conversation_id)

    async def get_for_update(self, conversation_id: uuid.UUID) -> Conversation | None:
        """Lock the conversation row so message sequence allocation is serialized."""
        result = await self._session.execute(
            select(Conversation).where(Conversation.id == conversation_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def delete(self, conversation_id: uuid.UUID) -> bool:
        conversation = await self.get(conversation_id)
        if conversation is None:
            return False
        await self._session.delete(conversation)
        await self._session.flush()
        return True

    async def touch(self, conversation_id: uuid.UUID) -> None:
        """Bump updated_at, which drives sidebar ordering."""
        await self._session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=datetime.now(UTC))
        )

    async def list_page(self, *, limit: int, cursor: Cursor | None = None) -> ConversationPage:
        """Keyset page ordered by updated_at DESC, id DESC."""
        statement = (
            select(Conversation)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .limit(limit + 1)
        )
        if cursor is not None:
            statement = statement.where(
                tuple_(Conversation.updated_at, Conversation.id)
                < tuple_(cursor.updated_at, cursor.id)
            )

        result = await self._session.execute(statement)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        return ConversationPage(items=rows[:limit], has_more=has_more)


class MessageRepository:
    """Message persistence with per-conversation sequence allocation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        conversation_id: uuid.UUID,
        role: Role,
        content: str,
    ) -> Message:
        """Append a message, allocating the next seq under a conversation lock."""
        next_seq = await self._next_seq(conversation_id)
        message = Message(
            conversation_id=conversation_id,
            role=role.value,
            content=content,
            seq=next_seq,
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def _next_seq(self, conversation_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(Message.seq), 0)).where(
                Message.conversation_id == conversation_id
            )
        )
        return int(result.scalar_one()) + 1

    async def get(self, message_id: uuid.UUID) -> Message | None:
        return await self._session.get(Message, message_id)

    async def list_for_conversation(self, conversation_id: uuid.UUID) -> Sequence[Message]:
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.seq.asc())
        )
        return list(result.scalars().all())


class AttemptRepository:
    """Generation attempt lifecycle metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        user_message_id: uuid.UUID,
        provider: str,
        model: str,
    ) -> GenerationAttempt:
        attempt_no = await self.next_attempt_no(user_message_id)
        attempt = GenerationAttempt(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            attempt_no=attempt_no,
            status=AttemptStatus.IN_PROGRESS.value,
            provider=provider,
            model=model,
        )
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def next_attempt_no(self, user_message_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(GenerationAttempt.attempt_no), 0)).where(
                GenerationAttempt.user_message_id == user_message_id
            )
        )
        return int(result.scalar_one()) + 1

    async def get(self, attempt_id: uuid.UUID) -> GenerationAttempt | None:
        return await self._session.get(GenerationAttempt, attempt_id)

    async def get_active_for_conversation(
        self, conversation_id: uuid.UUID
    ) -> GenerationAttempt | None:
        """Return the in-progress attempt, if any."""
        result = await self._session.execute(
            select(GenerationAttempt).where(
                GenerationAttempt.conversation_id == conversation_id,
                GenerationAttempt.status == AttemptStatus.IN_PROGRESS.value,
            )
        )
        return result.scalar_one_or_none()

    async def list_active_for_conversations(
        self, conversation_ids: Sequence[uuid.UUID]
    ) -> Sequence[GenerationAttempt]:
        """Return every in-progress attempt for the given conversations."""
        if not conversation_ids:
            return []
        result = await self._session.execute(
            select(GenerationAttempt).where(
                GenerationAttempt.conversation_id.in_(conversation_ids),
                GenerationAttempt.status == AttemptStatus.IN_PROGRESS.value,
            )
        )
        return list(result.scalars().all())

    async def list_for_conversation(
        self, conversation_id: uuid.UUID
    ) -> Sequence[GenerationAttempt]:
        result = await self._session.execute(
            select(GenerationAttempt)
            .where(GenerationAttempt.conversation_id == conversation_id)
            .order_by(GenerationAttempt.started_at.asc(), GenerationAttempt.attempt_no.asc())
        )
        return list(result.scalars().all())

    async def latest_for_user_message(self, user_message_id: uuid.UUID) -> GenerationAttempt | None:
        result = await self._session.execute(
            select(GenerationAttempt)
            .where(GenerationAttempt.user_message_id == user_message_id)
            .order_by(GenerationAttempt.attempt_no.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def has_completed_for_user_message(self, user_message_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            select(func.count())
            .select_from(GenerationAttempt)
            .where(
                GenerationAttempt.user_message_id == user_message_id,
                GenerationAttempt.status == AttemptStatus.COMPLETED.value,
            )
        )
        return int(result.scalar_one()) > 0

    async def finalize(
        self,
        attempt_id: uuid.UUID,
        *,
        status: AttemptStatus,
        assistant_message_id: uuid.UUID | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        usage: dict[str, Any] | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        thought_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        """Move an attempt to a terminal state and record its metadata."""
        await self._session.execute(
            update(GenerationAttempt)
            .where(GenerationAttempt.id == attempt_id)
            .values(
                status=status.value,
                assistant_message_id=assistant_message_id,
                error_code=error_code,
                error_message=error_message,
                usage_raw=usage,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thought_tokens=thought_tokens,
                total_tokens=total_tokens,
                completed_at=datetime.now(UTC),
            )
        )
