"""Message persistence with per-conversation sequence allocation."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lucid.domain.enums import Role
from lucid.persistence.tables import Message


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
