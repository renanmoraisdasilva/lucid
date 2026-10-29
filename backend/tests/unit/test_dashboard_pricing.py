"""Estimated API cost from configured list prices."""

from decimal import Decimal

from lucid.application.dashboard.pricing import Pricing
from lucid.config import Settings


def plan(input_rate: str | None, output_rate: str | None, *, free: bool = True) -> Pricing:
    return Pricing(
        input_usd_per_million=Decimal(input_rate) if input_rate is not None else None,
        output_usd_per_million=Decimal(output_rate) if output_rate is not None else None,
        free_tier=free,
    )


def test_estimates_and_rounds_to_cents() -> None:
    estimate = plan("0.30", "2.50").estimate_usd(input_tokens=283_100, output_tokens=83_300)

    # 0.08493 + 0.20825 = 0.29318, rounded to 0.29
    assert estimate == Decimal("0.29")


def test_zero_tokens_are_zero_not_missing() -> None:
    assert plan("1", "2").estimate_usd(input_tokens=0, output_tokens=0) == Decimal("0.00")


def test_missing_token_usage_makes_the_estimate_unavailable() -> None:
    prices = plan("0.30", "2.50")

    assert prices.available is True
    assert prices.estimate_usd(input_tokens=None, output_tokens=10) is None
    assert prices.estimate_usd(input_tokens=10, output_tokens=None) is None


def test_missing_rate_makes_pricing_unavailable() -> None:
    prices = plan("0.30", None)

    assert prices.available is False
    assert prices.estimate_usd(input_tokens=10, output_tokens=10) is None


def test_free_tier_still_uses_list_prices() -> None:
    prices = plan("0.30", "2.50", free=True)

    assert prices.free_tier is True
    assert prices.estimate_usd(input_tokens=1_000_000, output_tokens=1_000_000) == Decimal("2.80")


def test_from_settings_uses_decimal_strings() -> None:
    settings = Settings()
    settings.pricing_input_usd_per_million = 0.1
    settings.pricing_output_usd_per_million = 0.2
    settings.pricing_free_tier = False

    prices = Pricing.from_settings(settings)

    assert prices.input_usd_per_million == Decimal("0.1")
    assert prices.output_usd_per_million == Decimal("0.2")


def test_from_settings_allows_unconfigured_prices() -> None:
    settings = Settings()
    settings.pricing_input_usd_per_million = None
    settings.pricing_output_usd_per_million = None

    prices = Pricing.from_settings(settings)

    assert prices.available is False
