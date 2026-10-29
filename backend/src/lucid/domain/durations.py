"""Parsing provider wait hints such as ``21.2s``, ``2m``, or ``11h2m40s``."""

import re
from typing import Final

_DURATION_PART: Final = re.compile(r"(\d+(?:\.\d+)?)([hms])")
_UNIT_SECONDS: Final = {"h": 3600.0, "m": 60.0, "s": 1.0}


def parse_duration(text: str) -> float | None:
    """Return seconds for a provider duration string, or None if it has none."""
    total = 0.0
    found = False
    for value, unit in _DURATION_PART.findall(text):
        found = True
        total += float(value) * _UNIT_SECONDS[unit]
    return total if found else None


def parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header (numeric seconds) or a provider hint."""
    if not value:
        return None
    try:
        return max(0.0, float(value.strip()))
    except ValueError:
        return parse_duration(value)
