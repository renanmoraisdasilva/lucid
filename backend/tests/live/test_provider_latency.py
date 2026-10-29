"""Opt-in checks against the real provider.

These are skipped unless ``LUCID_LIVE_TESTS=1``. They exist because the fake
provider is instant, so no amount of deterministic testing catches a regression
in *provider* latency — which is exactly how a 25-second first token shipped.
"""

import os
import time

import pytest

from lucid.config import get_settings
from lucid.domain.enums import Role
from lucid.domain.provider import GenerationRequest, ProviderMessage, TextDelta
from lucid.providers.gemini import GeminiProvider

pytestmark = pytest.mark.live

FIRST_TOKEN_BUDGET_SECONDS = 5.0


@pytest.fixture(scope="module")
def provider() -> GeminiProvider:
    if os.environ.get("LUCID_LIVE_TESTS") != "1":
        pytest.skip("set LUCID_LIVE_TESTS=1 to run live provider checks")

    settings = get_settings()
    if settings.gemini_api_key is None:
        pytest.skip("GEMINI_API_KEY is not configured")

    return GeminiProvider(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.generation_timeout_seconds,
        max_output_tokens=64,
        thinking_level=settings.gemini_thinking_level,
    )


async def test_first_token_arrives_within_budget(provider: GeminiProvider) -> None:
    """Guards the latency of the configured model and thinking level."""
    request = GenerationRequest(
        model=get_settings().gemini_model,
        system_prompt="Answer with one short sentence.",
        messages=[ProviderMessage(role=Role.USER, content="Hi")],
        max_output_tokens=64,
        request_id="live-latency",
    )

    started = time.perf_counter()
    first_token: float | None = None

    async for event in provider.stream(request):
        if isinstance(event, TextDelta):
            first_token = time.perf_counter() - started
            break

    assert first_token is not None, "no text token was produced"
    assert first_token < FIRST_TOKEN_BUDGET_SECONDS, (
        f"first token took {first_token:.1f}s; check GEMINI_THINKING_LEVEL "
        f"(got {get_settings().gemini_thinking_level!r})"
    )
