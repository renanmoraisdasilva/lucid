"""HTTP request and response models."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

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
    error_message: str | None = None
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
    model_id: str | None = None


class RetryRequest(BaseModel):
    """Retry an existing user message, optionally with another model."""

    model_id: str | None = None


class ModelOptionOut(BaseModel):
    """One selectable model."""

    id: str
    label: str
    provider: str
    model: str


class ModelsResponse(BaseModel):
    """Models available to the picker."""

    items: list[ModelOptionOut]
    default_id: str


class StopGenerationResponse(BaseModel):
    """Result of a stop request. The stream still sends the terminal event."""

    attempt_id: uuid.UUID
    status: AttemptStatus
    stop_requested: bool


DashboardRangeValue = Literal["24h", "7d", "30d"]
DashboardBucketValue = Literal["hour", "day"]


class PricingOut(BaseModel):
    """Configured list prices and whether they are usable."""

    available: bool
    free_tier: bool
    input_usd_per_million: float | None = None
    output_usd_per_million: float | None = None


class OverviewOut(BaseModel):
    """Aggregates for the selected range."""

    conversations_active: int
    conversations_new: int
    user_messages: int
    attempts: int
    completed: int
    failed: int
    interrupted: int
    in_progress: int
    success_rate: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    average_input_tokens: int | None = None
    average_output_tokens: int | None = None
    usage_partial: bool = False
    estimated_cost_usd: float | None = None
    pricing: PricingOut


class TrendPointOut(BaseModel):
    """One hourly or daily bucket."""

    bucket_start: datetime
    attempts: int
    completed: int
    failed: int
    interrupted: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    ttft_ms_p50: float | None = None
    ttft_ms_p95: float | None = None
    duration_ms_p50: float | None = None
    duration_ms_p95: float | None = None


class LatencyStatsOut(BaseModel):
    """Percentiles plus the sample count behind them."""

    p50_ms: float | None = None
    p95_ms: float | None = None
    samples: int


class LatencyOut(BaseModel):
    ttft: LatencyStatsOut
    duration: LatencyStatsOut


class RecentAttemptOut(BaseModel):
    """Metadata for one recent attempt. Never contains message content."""

    attempt_id: uuid.UUID
    started_at: datetime
    conversation_id: uuid.UUID
    conversation_title: str
    status: AttemptStatus
    model: str
    attempt_no: int
    retry_count: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    ttft_ms: float | None = None
    duration_ms: float | None = None
    http_status: int | None = None
    context_tokens: int | None = None
    error_code: str | None = None
    error_message: str | None = None


class DashboardOut(BaseModel):
    """Everything the dashboard page needs for one refresh."""

    range: DashboardRangeValue
    generated_at: datetime
    bucket: DashboardBucketValue
    overview: OverviewOut
    trend: list[TrendPointOut]
    latency: LatencyOut
    recent: list[RecentAttemptOut]
