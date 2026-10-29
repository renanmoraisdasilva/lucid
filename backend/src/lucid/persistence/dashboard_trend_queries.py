"""Trend and latency aggregates for the dashboard."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lucid.application.dashboard.buckets import DashboardWindow
from lucid.application.dashboard.query_rows import LatencyRow, TrendRow
from lucid.domain.enums import AttemptStatus
from lucid.persistence.dashboard_sql import (
    bucket_expression,
    duration_ms,
    int_value,
    optional_float,
    optional_int,
    terminal_range,
    ttft_ms,
)
from lucid.persistence.tables import GenerationAttempt


def _trend_select(window: DashboardWindow):
    bucket = bucket_expression(window)
    ttft = ttft_ms()
    duration = duration_ms()
    return (
        select(
            bucket.label("bucket_start"),
            func.count(GenerationAttempt.id).label("attempts"),
            func.count(GenerationAttempt.id)
            .filter(GenerationAttempt.status == AttemptStatus.COMPLETED.value)
            .label("completed"),
            func.count(GenerationAttempt.id)
            .filter(GenerationAttempt.status == AttemptStatus.FAILED.value)
            .label("failed"),
            func.count(GenerationAttempt.id)
            .filter(GenerationAttempt.status == AttemptStatus.INTERRUPTED.value)
            .label("interrupted"),
            func.sum(GenerationAttempt.input_tokens).label("input_tokens"),
            func.sum(GenerationAttempt.output_tokens).label("output_tokens"),
            func.count(GenerationAttempt.input_tokens).label("input_samples"),
            func.count(GenerationAttempt.output_tokens).label("output_samples"),
            func.percentile_cont(0.5).within_group(ttft).label("ttft_p50"),
            func.percentile_cont(0.95).within_group(ttft).label("ttft_p95"),
            func.count(GenerationAttempt.first_token_at).label("ttft_samples"),
            func.percentile_cont(0.5).within_group(duration).label("duration_p50"),
            func.percentile_cont(0.95).within_group(duration).label("duration_p95"),
            func.count(GenerationAttempt.completed_at).label("duration_samples"),
        )
        .where(terminal_range(window))
        .group_by(bucket)
        .order_by(bucket)
    )


def _trend_row(row: Any) -> TrendRow:
    return TrendRow(
        bucket_start=cast(datetime, row.bucket_start),
        attempts=int_value(row.attempts),
        completed=int_value(row.completed),
        failed=int_value(row.failed),
        interrupted=int_value(row.interrupted),
        input_tokens=optional_int(row.input_tokens),
        output_tokens=optional_int(row.output_tokens),
        input_samples=int_value(row.input_samples),
        output_samples=int_value(row.output_samples),
        ttft_ms_p50=optional_float(row.ttft_p50),
        ttft_ms_p95=optional_float(row.ttft_p95),
        ttft_samples=int_value(row.ttft_samples),
        duration_ms_p50=optional_float(row.duration_p50),
        duration_ms_p95=optional_float(row.duration_p95),
        duration_samples=int_value(row.duration_samples),
    )


async def trend(session: AsyncSession, window: DashboardWindow) -> list[TrendRow]:
    """Per-bucket outcomes, tokens and latency percentiles."""
    rows = (await session.execute(_trend_select(window))).all()
    return [_trend_row(row) for row in rows]


async def latency(session: AsyncSession, window: DashboardWindow) -> LatencyRow:
    """Period-wide percentiles for TTFT and total duration."""
    ttft = ttft_ms()
    duration = duration_ms()
    row = (
        await session.execute(
            select(
                func.percentile_cont(0.5).within_group(ttft).label("ttft_p50"),
                func.percentile_cont(0.95).within_group(ttft).label("ttft_p95"),
                func.count(GenerationAttempt.first_token_at).label("ttft_samples"),
                func.percentile_cont(0.5).within_group(duration).label("duration_p50"),
                func.percentile_cont(0.95).within_group(duration).label("duration_p95"),
                func.count(GenerationAttempt.completed_at).label("duration_samples"),
            ).where(terminal_range(window))
        )
    ).one()

    return LatencyRow(
        ttft_ms_p50=optional_float(row.ttft_p50),
        ttft_ms_p95=optional_float(row.ttft_p95),
        ttft_samples=int_value(row.ttft_samples),
        duration_ms_p50=optional_float(row.duration_p50),
        duration_ms_p95=optional_float(row.duration_p95),
        duration_samples=int_value(row.duration_samples),
    )
