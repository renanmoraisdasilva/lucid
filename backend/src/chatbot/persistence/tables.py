"""SQLAlchemy models: conversations, messages, generation attempts.

Invariants live in the database, not only in application code:

- one in-progress attempt per conversation (partial unique index)
- dense, unique message ordering per conversation (UNIQUE (conversation_id, seq))
- one attempt number per user message (UNIQUE (user_message_id, attempt_no))
- deleting a conversation removes its messages and attempts (ON DELETE CASCADE)
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from chatbot.domain.enums import AttemptStatus
from chatbot.domain.ids import uuid7
from chatbot.persistence.db import Base

_ACTIVE_STATUS_PREDICATE = text("status = 'in_progress'")


class Conversation(Base):
    """A chat thread. Title is derived from the first user message."""

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 80", name="ck_conversations_title_len"),
        # Serves ORDER BY updated_at DESC, id DESC via a backward index scan.
        Index("ix_conversations_order", "updated_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Message(Base):
    """A single turn in a conversation. Canonical transcript content."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_messages_role"),
        CheckConstraint("char_length(content) > 0", name="ck_messages_content_not_empty"),
        UniqueConstraint("conversation_id", "seq", name="uq_messages_seq"),
        Index("ix_messages_conversation_seq", "conversation_id", "seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GenerationAttempt(Base):
    """One provider generation for one user message; text lives on the message."""

    __tablename__ = "generation_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress','completed','failed','interrupted')",
            name="ck_attempts_status",
        ),
        CheckConstraint("attempt_no >= 1", name="ck_attempts_attempt_no"),
        UniqueConstraint("user_message_id", "attempt_no", name="uq_attempts_attempt_no"),
        Index("ix_attempts_conversation", "conversation_id"),
        Index("ix_attempts_user_message", "user_message_id"),
        Index(
            "uq_attempts_one_active_per_conversation",
            "conversation_id",
            unique=True,
            postgresql_where=_ACTIVE_STATUS_PREDICATE,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    assistant_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=AttemptStatus.IN_PROGRESS.value
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thought_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["Conversation", "GenerationAttempt", "Message"]
