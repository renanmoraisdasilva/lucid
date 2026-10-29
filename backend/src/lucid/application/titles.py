"""Deterministic conversation titles derived from the first user message."""

import unicodedata

MAX_TITLE_CODE_POINTS = 80
WORD_BOUNDARY_WINDOW = 20
FALLBACK_TITLE = "New chat"
_TRAILING_PUNCTUATION = " ,.;:-"


def derive_title(text: str) -> str:
    """Build a conversation title from the first user message.

    Normalizes whitespace, truncates to 80 code points, and prefers cutting at a
    word boundary within the last 20 code points so titles do not end mid-word.
    """
    normalized = _normalize(text)
    if not normalized:
        return FALLBACK_TITLE

    if len(normalized) <= MAX_TITLE_CODE_POINTS:
        return normalized

    window = normalized[:MAX_TITLE_CODE_POINTS]
    boundary = _word_boundary(window)
    candidate = window[:boundary] if boundary > 0 else window
    candidate = candidate.rstrip(_TRAILING_PUNCTUATION).rstrip()
    return candidate or window


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    # Collapse whitespace first so newlines and tabs become single spaces rather
    # than disappearing and gluing words together.
    text = " ".join(text.split())
    text = "".join(
        character for character in text if not unicodedata.category(character).startswith("C")
    )
    return text.strip()


def _word_boundary(window: str) -> int:
    """Return the index after the last space in the trailing window, or 0."""
    search_from = max(0, len(window) - WORD_BOUNDARY_WINDOW)
    index = window.rfind(" ", search_from)
    return index if index > 0 else 0
