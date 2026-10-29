"""Final dashboard result types."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from lucid.application.dashboard.buckets import BucketSize, DashboardRange


@dataclass(frozen=True, slots=True)
class PricingInfo:
    available: bool
    free_tier: bool
    input_usd_per_million: float | None
    output_usd_per_million: float | None


@dataclass(frozen=True, slots=True)
class Overview:
    conversations_active: int
    conversations_new: int
    user_messages: int
    attempts: int
    completed: int
    failed: int
    interrupted: int
    in_progress: int
    success_rate: float | None
    input_tokens: int | None
    output_tokens: int | None
    usage_partial: bool
    estimated_cost_usd: float | None
    pricing: PricingInfo


@dataclass(frozen=True, slots=True)
class TrendPoint:
    bucket_start: datetime
    attempts: int
    completed: int
    failed: int
    interrupted: int
    input_tokens: int | None
    output_tokens: int | None
    ttft_ms_p50: float | None
    ttft_ms_p95: float | None
    duration_ms_p50: float | None
    duration_ms_p95: float | None


@dataclass(frozen=True, slots=True)
class LatencyStats:
    p50_ms: float | None
    p95_ms: float | None
    samples: int


@dataclass(frozen=True, slots=True)
class Latency:
    ttft: LatencyStats
    duration: LatencyStats


@dataclass(frozen=True, slots=True)
class RecentAttempt:
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
    ttft_ms: float | None
    duration_ms: float | None
    http_status: int | None
    context_tokens: int | None
    error_code: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class DashboardResult:
    range_key: DashboardRange
    generated_at: datetime
    bucket: BucketSize
    overview: Overview
    trend: list[TrendPoint]
    latency: Latency
    recent: list[RecentAttempt]
