"""Turn dashboard queries into the read model the API returns."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from lucid.application.dashboard.buckets import DashboardWindow
from lucid.application.dashboard.pricing import Pricing
from lucid.application.dashboard.query_rows import (
    LatencyRow,
    OverviewCounts,
    RecentRow,
    TrendRow,
)
from lucid.application.dashboard.results import (
    DashboardResult,
    Latency,
    LatencyStats,
    Overview,
    PricingInfo,
    RecentAttempt,
    TrendPoint,
)
from lucid.config import Settings
from lucid.persistence import dashboard_queries, dashboard_recent, dashboard_trend_queries

P95_MIN_SAMPLES = 20


def _ms(value: float | None) -> float | None:
    return round(float(value), 1) if value is not None else None


def _delta_ms(start: datetime, end: datetime | None) -> float | None:
    if end is None:
        return None
    return round((end - start).total_seconds() * 1000, 1)


def build_overview(counts: OverviewCounts, pricing: Pricing) -> Overview:
    """Apply partial-data and pricing rules to raw aggregates."""
    success_rate = round(counts.completed / counts.attempts, 4) if counts.attempts > 0 else None
    if counts.attempts == 0:
        input_tokens: int | None = 0
        output_tokens: int | None = 0
    else:
        input_tokens = counts.input_tokens if counts.input_samples > 0 else None
        output_tokens = counts.output_tokens if counts.output_samples > 0 else None

    estimate = pricing.estimate_usd(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    return Overview(
        conversations_active=counts.conversations_active,
        conversations_new=counts.conversations_new,
        user_messages=counts.user_messages,
        attempts=counts.attempts,
        completed=counts.completed,
        failed=counts.failed,
        interrupted=counts.interrupted,
        in_progress=counts.in_progress,
        success_rate=success_rate,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        usage_partial=counts.missing_usage > 0,
        estimated_cost_usd=float(estimate) if estimate is not None else None,
        pricing=PricingInfo(
            available=pricing.available,
            free_tier=pricing.free_tier,
            input_usd_per_million=(
                float(pricing.input_usd_per_million)
                if pricing.input_usd_per_million is not None
                else None
            ),
            output_usd_per_million=(
                float(pricing.output_usd_per_million)
                if pricing.output_usd_per_million is not None
                else None
            ),
        ),
    )


def build_trend(window: DashboardWindow, rows: list[TrendRow]) -> list[TrendPoint]:
    """Fill missing buckets and apply the p95 sample threshold."""
    by_bucket = {row.bucket_start.astimezone(UTC): row for row in rows}
    points: list[TrendPoint] = []
    for bucket_start in window.bucket_starts:
        row = by_bucket.get(bucket_start)
        if row is None:
            points.append(
                TrendPoint(
                    bucket_start=bucket_start,
                    attempts=0,
                    completed=0,
                    failed=0,
                    interrupted=0,
                    input_tokens=0,
                    output_tokens=0,
                    ttft_ms_p50=None,
                    ttft_ms_p95=None,
                    duration_ms_p50=None,
                    duration_ms_p95=None,
                )
            )
            continue

        input_tokens = (
            0 if row.attempts == 0 else (row.input_tokens if row.input_samples > 0 else None)
        )
        output_tokens = (
            0 if row.attempts == 0 else (row.output_tokens if row.output_samples > 0 else None)
        )
        points.append(
            TrendPoint(
                bucket_start=bucket_start,
                attempts=row.attempts,
                completed=row.completed,
                failed=row.failed,
                interrupted=row.interrupted,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                ttft_ms_p50=_ms(row.ttft_ms_p50),
                ttft_ms_p95=(_ms(row.ttft_ms_p95) if row.ttft_samples >= P95_MIN_SAMPLES else None),
                duration_ms_p50=_ms(row.duration_ms_p50),
                duration_ms_p95=(
                    _ms(row.duration_ms_p95) if row.duration_samples >= P95_MIN_SAMPLES else None
                ),
            )
        )
    return points


def build_latency(row: LatencyRow) -> Latency:
    return Latency(
        ttft=LatencyStats(
            p50_ms=_ms(row.ttft_ms_p50),
            p95_ms=_ms(row.ttft_ms_p95) if row.ttft_samples >= P95_MIN_SAMPLES else None,
            samples=row.ttft_samples,
        ),
        duration=LatencyStats(
            p50_ms=_ms(row.duration_ms_p50),
            p95_ms=(_ms(row.duration_ms_p95) if row.duration_samples >= P95_MIN_SAMPLES else None),
            samples=row.duration_samples,
        ),
    )


def build_recent(rows: list[RecentRow]) -> list[RecentAttempt]:
    return [
        RecentAttempt(
            attempt_id=row.attempt_id,
            started_at=row.started_at,
            conversation_id=row.conversation_id,
            conversation_title=row.conversation_title,
            status=row.status,
            model=row.model,
            attempt_no=row.attempt_no,
            retry_count=row.retry_count,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            ttft_ms=_delta_ms(row.started_at, row.first_token_at),
            duration_ms=_delta_ms(row.started_at, row.completed_at),
            http_status=row.http_status,
            context_tokens=row.context_tokens,
            error_code=row.error_code,
            error_message=row.error_message,
        )
        for row in rows
    ]


async def build_dashboard(
    session: AsyncSession,
    window: DashboardWindow,
    settings: Settings,
) -> DashboardResult:
    """Run the dashboard queries and assemble the response."""
    counts = await dashboard_queries.overview_counts(session, window)
    trend_rows = await dashboard_trend_queries.trend(session, window)
    latency_row = await dashboard_trend_queries.latency(session, window)
    recent_rows = await dashboard_recent.recent(session, window)
    pricing = Pricing.from_settings(settings)

    return DashboardResult(
        range_key=window.range_key,
        generated_at=window.end,
        bucket=window.bucket,
        overview=build_overview(counts, pricing),
        trend=build_trend(window, trend_rows),
        latency=build_latency(latency_row),
        recent=build_recent(recent_rows),
    )
