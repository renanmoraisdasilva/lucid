"""Rate-limit cooldown bookkeeping."""

from lucid.application.cooldown import DEFAULT_COOLDOWN_SECONDS, RateLimitCooldown


def test_counts_down_and_reports_remaining() -> None:
    now = [1_000.0]
    cooldown = RateLimitCooldown(clock=lambda: now[0])

    cooldown.record(60.0)

    assert cooldown.remaining() == 60.0
    now[0] += 30.0
    assert cooldown.remaining() == 30.0
    now[0] += 30.0
    assert cooldown.remaining() == 0.0


def test_defaults_when_the_provider_gives_no_hint() -> None:
    cooldown = RateLimitCooldown(clock=lambda: 0.0)

    cooldown.record(None)

    assert cooldown.remaining() == DEFAULT_COOLDOWN_SECONDS


def test_keeps_the_reason_across_requests() -> None:
    now = [0.0]
    cooldown = RateLimitCooldown(clock=lambda: now[0])

    cooldown.record(39_000.0, reason="The free-tier daily limit is reached.")

    assert cooldown.reason == "The free-tier daily limit is reached."


def test_extends_but_never_shortens() -> None:
    now = [0.0]
    cooldown = RateLimitCooldown(clock=lambda: now[0])

    cooldown.record(100.0)
    cooldown.record(10.0)

    assert cooldown.remaining() == 100.0


def test_clear_resets_everything() -> None:
    cooldown = RateLimitCooldown(clock=lambda: 0.0)
    cooldown.record(100.0, reason="reason")

    cooldown.clear()

    assert cooldown.remaining() == 0.0
    assert cooldown.reason is None
