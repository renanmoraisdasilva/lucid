"""System prompt loading.

The prompt is a version-controlled file, validated at startup so a missing or
empty file fails fast instead of producing a model call with no instructions.
"""

from functools import lru_cache
from pathlib import Path

from lucid.domain.errors import ConfigurationError

MAX_PROMPT_CHARACTERS = 20_000


@lru_cache(maxsize=4)
def load_system_prompt(path: Path) -> str:
    """Read and validate the system prompt."""
    if not path.exists():
        raise ConfigurationError(f"System prompt not found: {path}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ConfigurationError(f"System prompt is empty: {path}")
    if len(text) > MAX_PROMPT_CHARACTERS:
        raise ConfigurationError(
            f"System prompt is {len(text)} characters; the limit is {MAX_PROMPT_CHARACTERS}."
        )
    return text
