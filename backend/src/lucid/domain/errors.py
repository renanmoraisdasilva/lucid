"""Provider and configuration errors.

Every provider failure is translated into one of these types by the adapter, so
application code never sees SDK exceptions. Messages are user-safe: provider
internals belong in ``detail`` (logs only), never in the message.
"""


class ProviderError(Exception):
    """Base class for a failed model call."""

    code: str = "provider_error"
    retryable: bool = False
    default_message: str = "The model request failed."

    def __init__(self, message: str | None = None, *, detail: str | None = None) -> None:
        super().__init__(message or self.default_message)
        self.detail = detail


class ProviderRateLimited(ProviderError):
    code = "provider_rate_limited"
    retryable = True
    default_message = "The model is rate limited right now. Try again in a moment."


class ProviderTimeout(ProviderError):
    code = "provider_timeout"
    retryable = True
    default_message = "The model did not respond in time."


class ProviderUnavailable(ProviderError):
    code = "provider_unavailable"
    retryable = True
    default_message = "The model is temporarily unavailable."


class ProviderInvalidRequest(ProviderError):
    code = "provider_invalid_request"
    retryable = False
    default_message = "The model rejected this request."


class ProviderSafetyBlocked(ProviderError):
    code = "provider_safety_blocked"
    retryable = False
    default_message = "The model declined to answer this request."


class ProviderStreamError(ProviderError):
    code = "provider_stream_error"
    retryable = False
    default_message = "The model response ended unexpectedly."


class EmptyProviderResponse(ProviderError):
    """The provider finished without producing any text."""

    code = "empty_response"
    retryable = True
    default_message = "The model returned no text. Try again."


class ContextTooLarge(ProviderError):
    code = "context_too_large"
    retryable = False
    default_message = "This conversation is too long for the model."


class FirstTokenTimeout(ProviderTimeout):
    """No text arrived before the first-token deadline.

    Deliberately excluded from automatic retries: the provider is queued, so
    retrying only multiplies the wait. The manual Retry action still works.
    """


class ConfigurationError(RuntimeError):
    """Invalid or missing configuration detected at startup."""
