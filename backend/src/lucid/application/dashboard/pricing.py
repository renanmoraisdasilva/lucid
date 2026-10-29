"""Estimated API cost from configured list prices.

The provider reports tokens, not money. This module turns the configured rates
into a clearly-labelled estimate; it never presents the result as billing data.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from lucid.config import Settings

ONE_MILLION = Decimal(1_000_000)
CENTS = Decimal("0.01")


def _rate(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


@dataclass(frozen=True, slots=True)
class Pricing:
    """List prices for the configured model, or unavailable when not set."""

    input_usd_per_million: Decimal | None
    output_usd_per_million: Decimal | None
    free_tier: bool

    @classmethod
    def from_settings(cls, settings: Settings) -> "Pricing":
        return cls(
            input_usd_per_million=_rate(settings.pricing_input_usd_per_million),
            output_usd_per_million=_rate(settings.pricing_output_usd_per_million),
            free_tier=settings.pricing_free_tier,
        )

    @property
    def available(self) -> bool:
        return self.input_usd_per_million is not None and self.output_usd_per_million is not None

    def estimate_usd(
        self,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> Decimal | None:
        """Return a rounded estimate, or None when any input is missing."""
        rate_in = self.input_usd_per_million
        rate_out = self.output_usd_per_million
        if rate_in is None or rate_out is None or input_tokens is None or output_tokens is None:
            return None

        amount = (
            Decimal(input_tokens) * rate_in / ONE_MILLION
            + Decimal(output_tokens) * rate_out / ONE_MILLION
        )
        return amount.quantize(CENTS, rounding=ROUND_HALF_UP)
