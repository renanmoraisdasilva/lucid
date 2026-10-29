"""Dashboard result assembly: partial data, gaps and p95 thresholds."""

import uuid
from datetime import UTC, datetime, timedelta

from lucid.application.dashboard.buckets import DashboardRange, window_for
from lucid.application.dashboard.pricing import Pricing
from lucid.application.dashboard.query_rows import (
    LatencyRow,
    OverviewCounts,
    RecentRow,
    TrendRow,
)
from lucid.application.dashboard.service import (
    build_latency,
    build_overview,
    build_recent,
    build_trend,
)

NOW = datetime(2026, 10, 29, 15, 30, tzinfo=UTC)


def counts(**overrides: int | None) -> OverviewCounts:
    values: dict[str, int | None] = {
        "conversations_active": 0,
        "conversations_new": 0,
        "user_messages": 0,
        "attempts": 0,
        "completed": 0,
        "failed": 0,
        "interrupted": 0,
        "in_progress": 0,
        "input_tokens": None,
        "output_tokens": None,
        "input_samples": 0,
        "output_samples": 0,
        "missing_usage": 0,
    }
    values.update(overrides)
    return OverviewCounts(**values)  # type: ignore[arg-type]


def prices(input_rate: str | None = "0.30", output_rate: str | None = "2.50") -> Pricing:
    from decimal import Decimal

    return Pricing(
        input_usd_per_million=Decimal(input_rate) if input_rate else None,
        output_usd_per_million=Decimal(output_rate) if output_rate else None,
        free_tier=True,
    )


def trend_row(**overrides: object) -> TrendRow:
    values: dict[str, object] = {
        "bucket_start": NOW,
        "attempts": 1,
        "completed": 1,
        "failed": 0,
        "interrupted": 0,
        "input_tokens": 100,
        "output_tokens": 20,
        "input_samples": 1,
        "output_samples": 1,
        "ttft_ms_p50": 400.0,
        "ttft_ms_p95": 900.0,
        "ttft_samples": 20,
        "duration_ms_p50": 2000.0,
        "duration_ms_p95": 4000.0,
        "duration_samples": 20,
    }
    values.update(overrides)
    return TrendRow(**values)  # type: ignore[arg-type]


def test_empty_overview_has_zero_tokens_and_no_rate() -> None:
    overview = build_overview(counts(), prices())

    assert overview.attempts == 0
    assert overview.success_rate is None
    assert overview.input_tokens == 0
    assert overview.output_tokens == 0
    assert overview.usage_partial is False
    assert overview.estimated_cost_usd == 0.0


def test_overview_keeps_the_available_token_field_when_usage_is_partial() -> None:
    overview = build_overview(
        counts(
            attempts=1,
            completed=1,
            input_tokens=100,
            output_tokens=None,
            input_samples=1,
            output_samples=0,
            missing_usage=1,
        ),
        prices(),
    )

    assert overview.input_tokens == 100
    assert overview.output_tokens is None
    assert overview.usage_partial is True
    assert overview.estimated_cost_usd is None


def test_success_rate_uses_only_terminal_attempts() -> None:
    overview = build_overview(
        counts(attempts=4, completed=3, failed=1, in_progress=2),
        prices(),
    )

    assert overview.success_rate == 0.75
    assert overview.in_progress == 2


def test_overview_cost_is_rounded_from_list_prices() -> None:
    overview = build_overview(
        counts(
            attempts=1,
            completed=1,
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            input_samples=1,
            output_samples=1,
        ),
        prices(),
    )

    assert overview.estimated_cost_usd == 2.8
    assert overview.pricing.available is True
    assert overview.pricing.input_usd_per_million == 0.3


def test_averages_use_only_attempts_with_usage() -> None:
    overview = build_overview(
        counts(
            attempts=3,
            completed=3,
            input_tokens=300,
            output_tokens=80,
            input_samples=2,
            output_samples=2,
        ),
        prices(),
    )

    assert overview.average_input_tokens == 150
    assert overview.average_output_tokens == 40


def test_overview_cost_is_unavailable_without_prices() -> None:
    overview = build_overview(
        counts(attempts=1, completed=1, input_tokens=10, output_tokens=10),
        prices(None, None),
    )

    assert overview.estimated_cost_usd is None
    assert overview.pricing.available is False


def test_trend_fills_missing_buckets_and_keeps_real_zeros() -> None:
    window = window_for(DashboardRange.WEEK, NOW)
    rows = [
        trend_row(
            bucket_start=window.bucket_starts[0],
            attempts=2,
            input_tokens=50,
            input_samples=2,
            output_tokens=None,
            output_samples=0,
            ttft_samples=20,
            duration_samples=19,
        )
    ]

    points = build_trend(window, rows)

    assert len(points) == 7
    assert points[0].attempts == 2
    assert points[0].input_tokens == 50
    assert points[0].output_tokens is None
    assert points[0].ttft_ms_p95 == 900.0
    assert points[0].duration_ms_p95 is None
    assert points[1].attempts == 0
    assert points[1].input_tokens == 0
    assert points[1].ttft_ms_p50 is None


def test_trend_nulls_tokens_when_attempts_have_no_usage() -> None:
    window = window_for(DashboardRange.WEEK, NOW)
    points = build_trend(
        window,
        [
            trend_row(
                bucket_start=window.bucket_starts[0],
                input_tokens=None,
                output_tokens=None,
                input_samples=0,
                output_samples=0,
            )
        ],
    )

    assert points[0].input_tokens is None
    assert points[0].output_tokens is None


def test_latency_p95_needs_twenty_samples() -> None:
    few = build_latency(
        LatencyRow(
            ttft_ms_p50=100.0,
            ttft_ms_p95=200.0,
            ttft_samples=19,
            duration_ms_p50=1000.0,
            duration_ms_p95=2000.0,
            duration_samples=20,
        )
    )

    assert few.ttft.p95_ms is None
    assert few.duration.p95_ms == 2000.0


def test_recent_computes_ttft_and_duration() -> None:
    started = NOW - timedelta(minutes=5)
    recent = build_recent(
        [
            RecentRow(
                attempt_id=uuid.uuid4(),
                started_at=started,
                conversation_id=uuid.uuid4(),
                conversation_title="Title",
                status="completed",
                model="fake-model",
                attempt_no=1,
                retry_count=0,
                input_tokens=10,
                output_tokens=2,
                first_token_at=started + timedelta(milliseconds=400),
                completed_at=started + timedelta(milliseconds=2600),
                http_status=200,
                context_tokens=10,
                error_code=None,
                error_message=None,
            )
        ]
    )

    assert recent[0].ttft_ms == 400.0
    assert recent[0].duration_ms == 2600.0
