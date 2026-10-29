"""Context-window selection."""

import pytest

from lucid.application.context import (
    MESSAGE_OVERHEAD_TOKENS,
    ContextBudget,
    estimate_tokens,
    select_history,
)
from lucid.domain.enums import Role
from lucid.domain.errors import ContextTooLarge
from lucid.domain.provider import ProviderMessage


def message(role: Role, characters: int) -> ProviderMessage:
    return ProviderMessage(role=role, content="x" * characters)


def budget(**overrides: int) -> ContextBudget:
    values: dict[str, int] = {
        "max_input_tokens": 1000,
        "reserved_output_tokens": 0,
        "safety_margin_tokens": 0,
        "max_messages": 60,
    }
    values.update(overrides)
    return ContextBudget(**values)


def test_estimates_four_characters_per_token() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2
    assert estimate_tokens("x" * 400) == 100


def test_keeps_everything_that_fits() -> None:
    history = [message(Role.USER, 100), message(Role.ASSISTANT, 100), message(Role.USER, 100)]

    selected = select_history(history, system_prompt="sys", budget=budget()).messages

    assert selected == history


def test_drops_the_oldest_messages_first() -> None:
    oldest = message(Role.USER, 400)
    middle = message(Role.ASSISTANT, 400)
    newest = message(Role.USER, 400)

    selected = select_history(
        [oldest, middle, newest],
        system_prompt="sys",
        budget=budget(max_input_tokens=250, reserved_output_tokens=100),
    ).messages

    assert selected == [newest]


def test_drops_a_leading_assistant_turn() -> None:
    history = [message(Role.ASSISTANT, 20), message(Role.USER, 20)]

    selected = select_history(history, system_prompt="sys", budget=budget()).messages

    assert [item.role for item in selected] == [Role.USER]


def test_respects_the_message_cap() -> None:
    history = [
        message(Role.USER, 20),
        message(Role.ASSISTANT, 20),
        message(Role.USER, 20),
        message(Role.ASSISTANT, 20),
        message(Role.USER, 20),
    ]

    selected = select_history(history, system_prompt="sys", budget=budget(max_messages=3)).messages

    assert len(selected) == 3
    assert selected[-1] is history[-1]


def test_newest_message_must_always_fit() -> None:
    history = [message(Role.USER, 4000)]

    with pytest.raises(ContextTooLarge):
        select_history(
            history,
            system_prompt="sys",
            budget=budget(max_input_tokens=250, reserved_output_tokens=100),
        )


def test_system_prompt_consumes_budget() -> None:
    # 4400 characters is ~1100 estimated tokens, exactly the history budget below.
    long_prompt = "s" * 4400

    with pytest.raises(ContextTooLarge):
        select_history(
            [message(Role.USER, 20)],
            system_prompt=long_prompt,
            budget=budget(max_input_tokens=1200, reserved_output_tokens=100),
        )


def test_empty_history_is_rejected() -> None:
    with pytest.raises(ContextTooLarge):
        select_history([], system_prompt="sys", budget=budget())


def test_history_ending_with_assistant_is_rejected() -> None:
    with pytest.raises(ContextTooLarge):
        select_history(
            [message(Role.USER, 20), message(Role.ASSISTANT, 20)],
            system_prompt="sys",
            budget=budget(),
        )


def test_overhead_is_counted_per_message() -> None:
    # 250 characters = 63 estimated tokens, plus 4 overhead each = 67.
    history = [message(Role.USER, 250), message(Role.USER, 250)]

    selected = select_history(
        history,
        system_prompt="",
        budget=budget(max_input_tokens=120, reserved_output_tokens=0),
    ).messages

    assert len(selected) == 1
    assert MESSAGE_OVERHEAD_TOKENS == 4


def test_reports_the_estimated_prompt_size() -> None:
    selection = select_history(
        [message(Role.USER, 100)],
        system_prompt="sys",
        budget=budget(),
    )

    expected = estimate_tokens("sys") + estimate_tokens("x" * 100) + MESSAGE_OVERHEAD_TOKENS
    assert selection.estimated_tokens == expected


def test_history_budget_excludes_reserved_output() -> None:
    context = budget(max_input_tokens=1000, reserved_output_tokens=400, safety_margin_tokens=100)

    assert context.history_tokens == 500
