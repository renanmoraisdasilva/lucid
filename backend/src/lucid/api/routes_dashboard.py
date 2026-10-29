"""Read-only dashboard endpoint."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from lucid.api.deps import SessionDep
from lucid.api.schemas import (
    DashboardOut,
    LatencyOut,
    LatencyStatsOut,
    OverviewOut,
    PricingOut,
    RecentAttemptOut,
    TrendPointOut,
)
from lucid.application.dashboard.buckets import DashboardRange, window_for
from lucid.application.dashboard.results import (
    DashboardResult,
    Latency,
    Overview,
    RecentAttempt,
    TrendPoint,
)
from lucid.application.dashboard.service import build_dashboard
from lucid.config import get_settings
from lucid.domain.enums import AttemptStatus

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    session: SessionDep,
    date_range: Annotated[DashboardRange, Query(alias="range")] = DashboardRange.WEEK,
) -> DashboardOut:
    """Aggregates for the selected range. This endpoint never writes."""
    window = window_for(date_range, datetime.now(UTC))
    result = await build_dashboard(session, window, get_settings())
    return _to_response(result)


def _to_response(result: DashboardResult) -> DashboardOut:
    return DashboardOut(
        range=result.range_key.value,
        generated_at=result.generated_at,
        bucket=result.bucket.value,
        overview=_overview_out(result.overview),
        trend=[_trend_out(point) for point in result.trend],
        latency=_latency_out(result.latency),
        recent=[_recent_out(row) for row in result.recent],
    )


def _overview_out(overview: Overview) -> OverviewOut:
    return OverviewOut(
        conversations_active=overview.conversations_active,
        conversations_new=overview.conversations_new,
        user_messages=overview.user_messages,
        attempts=overview.attempts,
        completed=overview.completed,
        failed=overview.failed,
        interrupted=overview.interrupted,
        in_progress=overview.in_progress,
        success_rate=overview.success_rate,
        input_tokens=overview.input_tokens,
        output_tokens=overview.output_tokens,
        usage_partial=overview.usage_partial,
        estimated_cost_usd=overview.estimated_cost_usd,
        pricing=PricingOut(
            available=overview.pricing.available,
            free_tier=overview.pricing.free_tier,
            input_usd_per_million=overview.pricing.input_usd_per_million,
            output_usd_per_million=overview.pricing.output_usd_per_million,
        ),
    )


def _trend_out(point: TrendPoint) -> TrendPointOut:
    return TrendPointOut(
        bucket_start=point.bucket_start,
        attempts=point.attempts,
        completed=point.completed,
        failed=point.failed,
        interrupted=point.interrupted,
        input_tokens=point.input_tokens,
        output_tokens=point.output_tokens,
        ttft_ms_p50=point.ttft_ms_p50,
        ttft_ms_p95=point.ttft_ms_p95,
        duration_ms_p50=point.duration_ms_p50,
        duration_ms_p95=point.duration_ms_p95,
    )


def _latency_out(latency: Latency) -> LatencyOut:
    return LatencyOut(
        ttft=LatencyStatsOut(
            p50_ms=latency.ttft.p50_ms,
            p95_ms=latency.ttft.p95_ms,
            samples=latency.ttft.samples,
        ),
        duration=LatencyStatsOut(
            p50_ms=latency.duration.p50_ms,
            p95_ms=latency.duration.p95_ms,
            samples=latency.duration.samples,
        ),
    )


def _recent_out(row: RecentAttempt) -> RecentAttemptOut:
    return RecentAttemptOut(
        attempt_id=row.attempt_id,
        started_at=row.started_at,
        conversation_id=row.conversation_id,
        conversation_title=row.conversation_title,
        status=AttemptStatus(row.status),
        model=row.model,
        attempt_no=row.attempt_no,
        retry_count=row.retry_count,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        ttft_ms=row.ttft_ms,
        duration_ms=row.duration_ms,
        http_status=row.http_status,
        context_tokens=row.context_tokens,
        error_code=row.error_code,
        error_message=row.error_message,
    )
