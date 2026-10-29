"""Shared SQL expressions and value converters for dashboard queries."""

from typing import Any

from sqlalchemy import and_, func, text

from lucid.application.dashboard.buckets import BucketSize, DashboardWindow
from lucid.domain.enums import AttemptStatus
from lucid.persistence.tables import GenerationAttempt


def range_filter(window: DashboardWindow):
    return and_(
        GenerationAttempt.started_at >= window.start,
        GenerationAttempt.started_at < window.end,
    )


def terminal_range(window: DashboardWindow):
    return and_(
        range_filter(window),
        GenerationAttempt.status != AttemptStatus.IN_PROGRESS.value,
    )


def bucket_expression(window: DashboardWindow):
    if window.bucket is BucketSize.HOUR:
        return func.date_bin(text("interval '1 hour'"), GenerationAttempt.started_at, window.start)
    return func.date_trunc("day", GenerationAttempt.started_at, "UTC")


def milliseconds(column: Any) -> Any:
    return func.extract("epoch", column) * 1000.0


def ttft_ms():
    return milliseconds(GenerationAttempt.first_token_at - GenerationAttempt.started_at)


def duration_ms():
    return milliseconds(GenerationAttempt.completed_at - GenerationAttempt.started_at)


def int_value(value: Any) -> int:
    return int(value or 0)


def optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None
