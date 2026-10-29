"""HTTP request and response models."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from lucid.domain.enums import AttemptStatus, Role

MessageContent = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16_000)
]


class UsageOut(BaseModel):
    """Provider-reported token usage. Any field may be unknown."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    thought_tokens: int | None = None
    total_tokens: int | None = None


class AttemptSummary(BaseModel):
    """Lifecycle metadata for a generation attempt.

    ``retryable`` is only meaningful on a user message: it says whether the Retry
    action should be offered for that message. It is always false on assistant
    messages, whose content already exists.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: AttemptStatus
    model: str
    attempt_no: int
    retryable: bool = False
    error_code: str | None = None
    usage: UsageOut | None = None


class MessageOut(BaseModel):
    """One message in a transcript."""

    id: uuid.UUID
    role: Role
    seq: int
    content: str
    created_at: datetime
    attempt: AttemptSummary | None = None


class ConversationSummary(BaseModel):
    """A conversation as shown in the sidebar."""

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    active_attempt_id: uuid.UUID | None = None


class ConversationListResponse(BaseModel):
    """One page of conversations."""

    items: list[ConversationSummary]
    next_cursor: str | None = None
    has_more: bool = False


class ConversationDetail(ConversationSummary):
    """A conversation with its full transcript."""

    messages: list[MessageOut] = Field(default_factory=list[MessageOut])


class ErrorBody(BaseModel):
    """Inner error object."""

    code: str
    message: str
    details: dict[str, object] | None = None


class ErrorResponse(BaseModel):
    """Top-level error envelope."""

    error: ErrorBody


class ChatRequest(BaseModel):
    """Send a message, creating the conversation when no id is given."""

    conversation_id: uuid.UUID | None = None
    content: MessageContent


class ChatResponse(BaseModel):
    """Complete (non-streaming) reply from the temporary Milestone 3 endpoint."""

    conversation_id: uuid.UUID
    user_message_id: uuid.UUID
    attempt_id: uuid.UUID
    assistant_message_id: uuid.UUID | None = None
    attempt_status: AttemptStatus
    content: str
    usage: UsageOut | None = None
