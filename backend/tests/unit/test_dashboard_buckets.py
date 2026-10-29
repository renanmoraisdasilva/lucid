"""Range windows and bucket boundaries."""

from datetime import UTC, datetime, timedelta, timezone

from lucid.application.dashboard.buckets import BucketSize, DashboardRange, window_for

NOW = datetime(2026, 10, 29, 15, 30, tzinfo=UTC)


def test_24h_is_24_rolling_hourly_buckets() -> None:
    window = window_for(DashboardRange.DAY, NOW)

    assert window.bucket is BucketSize.HOUR
    assert window.start == NOW - timedelta(hours=24)
    assert window.end == NOW
    assert len(window.bucket_starts) == 24
    assert window.bucket_starts[0] == window.start
    assert window.bucket_starts[-1] == window.start + timedelta(hours=23)


def test_7d_is_seven_calendar_days_ending_today() -> None:
    window = window_for(DashboardRange.WEEK, NOW)

    assert window.bucket is BucketSize.DAY
    assert window.start == datetime(2026, 10, 23, tzinfo=UTC)
    assert window.end == NOW
    assert len(window.bucket_starts) == 7
    assert window.bucket_starts[-1] == datetime(2026, 10, 29, tzinfo=UTC)


def test_30d_is_thirty_calendar_days() -> None:
    window = window_for(DashboardRange.MONTH, NOW)

    assert window.start == datetime(2026, 9, 30, tzinfo=UTC)
    assert len(window.bucket_starts) == 30


def test_window_normalizes_to_utc() -> None:
    local = NOW.astimezone(timezone(timedelta(hours=-3)))

    window = window_for(DashboardRange.DAY, local)

    assert window.end == NOW
    assert window.end.tzinfo is UTC
