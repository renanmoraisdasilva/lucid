"""Provider-independent settings for one generation stream."""

from dataclasses import dataclass, field

from lucid.application.context import ContextBudget
from lucid.application.cooldown import RateLimitCooldown
from lucid.application.retry import RetryPolicy


@dataclass(frozen=True, slots=True)
class GenerationOptions:
    """Everything the stream needs besides the attempt and the provider."""

    system_prompt: str
    model: str
    max_output_tokens: int
    context_budget: ContextBudget = field(default_factory=ContextBudget)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    first_token_timeout: float | None = None
    cooldown: RateLimitCooldown | None = None
