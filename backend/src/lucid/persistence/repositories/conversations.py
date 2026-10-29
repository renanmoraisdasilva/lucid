"""Conversation reads and writes."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from lucid.application.cursor import Cursor
from lucid.application.titles import derive_title
from lucid.persistence.tables import Conversation


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
