"""Raw row types returned by dashboard SQL."""

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class OverviewCounts:
    """Raw aggregates before pricing and partial-data decisions."""

    conversations_active: int
    conversations_new: int
    user_messages: int
    attempts: int
    completed: int
    failed: int
    interrupted: int
    in_progress: int
    input_tokens: int | None
    output_tokens: int | None
    input_samples: int
    output_samples: int
    missing_usage: int


@dataclass(frozen=True, slots=True)
class TrendRow:
    """One bucket returned by SQL."""

    bucket_start: datetime
    attempts: int
    completed: int
    failed: int
    interrupted: int
    input_tokens: int | None
    output_tokens: int | None
    input_samples: int
    output_samples: int
    ttft_ms_p50: float | None
    ttft_ms_p95: float | None
    ttft_samples: int
    duration_ms_p50: float | None
    duration_ms_p95: float | None
    duration_samples: int


@dataclass(frozen=True, slots=True)
class LatencyRow:
    ttft_ms_p50: float | None
    ttft_ms_p95: float | None
    ttft_samples: int
    duration_ms_p50: float | None
    duration_ms_p95: float | None
    duration_samples: int


@dataclass(frozen=True, slots=True)
class RecentRow:
    attempt_id: uuid.UUID
    started_at: datetime
    conversation_id: uuid.UUID
    conversation_title: str
    status: str
    model: str
    attempt_no: int
    retry_count: int
    input_tokens: int | None
    output_tokens: int | None
    first_token_at: datetime | None
    completed_at: datetime | None
    http_status: int | None
    context_tokens: int | None
    error_code: str | None
    error_message: str | None
