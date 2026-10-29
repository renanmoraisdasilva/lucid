"""System prompt loading."""

from pathlib import Path

import pytest

from lucid.application.prompts import MAX_PROMPT_CHARACTERS, load_system_prompt
from lucid.domain.errors import ConfigurationError


def test_loads_and_strips_the_prompt(tmp_path: Path) -> None:
    path = tmp_path / "system.md"
    path.write_text("  be helpful \n", encoding="utf-8")

    assert load_system_prompt(path) == "be helpful"


def test_missing_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_system_prompt(tmp_path / "missing.md")


def test_empty_file_fails(tmp_path: Path) -> None:
    path = tmp_path / "system.md"
    path.write_text("   \n\t ", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_system_prompt(path)


def test_oversized_prompt_fails(tmp_path: Path) -> None:
    path = tmp_path / "system.md"
    path.write_text("x" * (MAX_PROMPT_CHARACTERS + 1), encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_system_prompt(path)


def test_repository_prompt_is_valid() -> None:
    path = Path(__file__).resolve().parents[2] / "prompts" / "system.md"

    prompt = load_system_prompt(path)

    assert "Lucid" in prompt
    assert len(prompt) <= MAX_PROMPT_CHARACTERS
