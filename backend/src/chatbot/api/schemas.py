"""HTTP request and response models."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from chatbot.domain.enums import AttemptStatus, Role


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
