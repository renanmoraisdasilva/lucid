"""Retry eligibility and backoff."""

import pytest

from lucid.application.retry import RetryPolicy
from lucid.domain.errors import (
    ProviderInvalidRequest,
    ProviderRateLimited,
    ProviderStreamError,
    ProviderTimeout,
    ProviderUnavailable,
)

POLICY = RetryPolicy(max_retries=2, base_delay_ms=1000, max_delay_ms=8000, jitter=False)


@pytest.mark.parametrize(
    "error",
    [ProviderRateLimited(), ProviderTimeout(), ProviderUnavailable()],
)
def test_transient_failures_are_retryable_before_output(error: Exception) -> None:
    assert POLICY.is_retryable(error, has_output=False) is True  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "error",
    [ProviderRateLimited(), ProviderTimeout(), ProviderUnavailable()],
)
def test_transient_failures_are_not_retried_after_output(error: Exception) -> None:
    assert POLICY.is_retryable(error, has_output=True) is False  # type: ignore[arg-type]


@pytest.mark.parametrize("error", [ProviderInvalidRequest(), ProviderStreamError()])
def test_permanent_failures_are_never_retried(error: Exception) -> None:
    assert POLICY.is_retryable(error, has_output=False) is False  # type: ignore[arg-type]


def test_backoff_doubles_and_caps() -> None:
    assert POLICY.delay_seconds(0) == 1.0
    assert POLICY.delay_seconds(1) == 2.0
    assert POLICY.delay_seconds(2) == 4.0
    assert POLICY.delay_seconds(3) == 8.0
    assert POLICY.delay_seconds(10) == 8.0


def test_jitter_stays_within_half_and_full_delay() -> None:
    policy = RetryPolicy(base_delay_ms=1000, jitter=True)

    assert policy.delay_seconds(0, rand=lambda: 0.0) == 0.5
    assert policy.delay_seconds(0, rand=lambda: 1.0) == 1.0
    assert 0.5 <= policy.delay_seconds(1, rand=lambda: 0.5) <= 2.0


def test_defaults_match_the_spec() -> None:
    policy = RetryPolicy()

    assert policy.max_retries == 2
    assert policy.base_delay_ms == 1000
    assert policy.max_delay_ms == 8000
    assert policy.jitter is True
