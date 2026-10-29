"""Date ranges and bucket boundaries for the dashboard."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class DashboardRange(StrEnum):
    """The three supported ranges."""

    DAY = "24h"
    WEEK = "7d"
    MONTH = "30d"


class BucketSize(StrEnum):
    HOUR = "hour"
    DAY = "day"


@dataclass(frozen=True, slots=True)
class DashboardWindow:
    """A half-open range and the buckets its trend chart uses."""

    range_key: DashboardRange
    start: datetime
    end: datetime
    bucket: BucketSize
    bucket_starts: tuple[datetime, ...]


def window_for(range_key: DashboardRange, now: datetime) -> DashboardWindow:
    """Build the query window.

    24 hours is a rolling window with 24 one-hour slots. 7 and 30 days are
    calendar-day windows ending today (UTC), so the chart has exactly 7 or 30
    day buckets and today is partial.
    """
    end = now.astimezone(UTC)
    if range_key is DashboardRange.DAY:
        start = end - timedelta(hours=24)
        starts = tuple(start + timedelta(hours=index) for index in range(24))
        return DashboardWindow(range_key, start, end, BucketSize.HOUR, starts)

    days = 7 if range_key is DashboardRange.WEEK else 30
    today = end.replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=days - 1)
    starts = tuple(start + timedelta(days=index) for index in range(days))
    return DashboardWindow(range_key, start, end, BucketSize.DAY, starts)
