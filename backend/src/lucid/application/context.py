"""Context-window selection.

The full conversation is always stored; only a bounded slice is sent to the
model. Selection uses local token estimates, which are never presented as
provider truth — provider usage metadata is what gets stored and displayed.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil

from lucid.domain.enums import Role
from lucid.domain.errors import ContextTooLarge
from lucid.domain.provider import ProviderMessage

MESSAGE_OVERHEAD_TOKENS = 4


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """Limits applied when building one provider request."""

    max_input_tokens: int = 20_000
    reserved_output_tokens: int = 4_096
    safety_margin_tokens: int = 512
    max_messages: int = 60

    @property
    def history_tokens(self) -> int:
        """Tokens available to the system prompt plus history."""
        return self.max_input_tokens - self.reserved_output_tokens - self.safety_margin_tokens


@dataclass(frozen=True, slots=True)
class ContextSelection:
    """The provider messages that fit, plus the app-side prompt estimate."""

    messages: list[ProviderMessage]
    estimated_tokens: int


def estimate_tokens(text: str) -> int:
    """Rough token estimate: four characters per token, rounded up.

    Deliberately conservative and cheap. The provider's reported usage is the
    only number the application treats as exact.
    """
    return max(1, ceil(len(text) / 4))


def select_history(
    history: Sequence[ProviderMessage],
    *,
    system_prompt: str,
    budget: ContextBudget,
) -> ContextSelection:
    """Return the newest messages that fit the budget.

    Always includes the newest message, never starts with an assistant turn, and
    raises ``ContextTooLarge`` rather than silently truncating the user's text.
    """
    available = budget.history_tokens - estimate_tokens(system_prompt)
    if available <= 0:
        raise ContextTooLarge("The system prompt alone exceeds the configured input budget.")

    selected: list[ProviderMessage] = []
    used = 0
    for message in reversed(history):
        cost = estimate_tokens(message.content) + MESSAGE_OVERHEAD_TOKENS
        if len(selected) >= budget.max_messages or used + cost > available:
            break
        selected.append(message)
        used += cost

    selected.reverse()

    # A transcript must begin with a user turn; drop a dangling assistant reply.
    while selected and selected[0].role is Role.ASSISTANT:
        selected.pop(0)

    if not selected or selected[-1].role is not Role.USER:
        raise ContextTooLarge("The newest message does not fit in the configured input budget.")

    estimated = estimate_tokens(system_prompt) + sum(
        estimate_tokens(item.content) + MESSAGE_OVERHEAD_TOKENS for item in selected
    )
    return ContextSelection(messages=selected, estimated_tokens=estimated)
