"""Model catalogue exposed to the UI.

Options exist only for providers that are configured, so the picker never offers
a model that would fail immediately. The default is the configured provider's
model when available, otherwise the first available option.
"""

from dataclasses import dataclass

from lucid.config import Settings


@dataclass(frozen=True, slots=True)
class ModelOption:
    """One selectable model."""

    id: str
    label: str
    provider: str
    model: str


@dataclass(frozen=True, slots=True)
class ModelCatalog:
    """Available models and the default selection."""

    options: tuple[ModelOption, ...]
    default_id: str

    def find(self, model_id: str | None) -> ModelOption | None:
        """Resolve a requested id, or the default when none is given."""
        if model_id is None:
            return self.by_id(self.default_id)
        return self.by_id(model_id)

    def by_id(self, model_id: str) -> ModelOption | None:
        return next((option for option in self.options if option.id == model_id), None)


def build_catalog(settings: Settings) -> ModelCatalog:
    """Build the catalogue from configured providers."""
    options: list[ModelOption] = []

    if settings.gemini_api_key is not None:
        options.append(
            ModelOption(
                id=f"gemini:{settings.gemini_model}",
                label=f"{settings.gemini_model} · Gemini",
                provider="gemini",
                model=settings.gemini_model,
            )
        )

    if settings.openai_api_key is not None:
        for model in settings.openai_model_list:
            options.append(
                ModelOption(
                    id=f"openai:{model}",
                    label=f"{model} · {_endpoint_name(settings.openai_base_url)}",
                    provider="openai_compatible",
                    model=model,
                )
            )

    if not options:
        options.append(
            ModelOption(
                id="fake:fake-model",
                label="Scripted provider",
                provider="fake",
                model="fake-model",
            )
        )

    preferred = _preferred_id(settings)
    default_id = preferred if any(o.id == preferred for o in options) else options[0].id
    return ModelCatalog(options=tuple(options), default_id=default_id)


def _preferred_id(settings: Settings) -> str:
    if settings.provider == "gemini":
        return f"gemini:{settings.gemini_model}"
    if settings.provider == "openai_compatible":
        return f"openai:{settings.default_openai_model}"
    return "fake:fake-model"


def _endpoint_name(base_url: str) -> str:
    """A short, human label for the endpoint host."""
    host = base_url.split("://", 1)[-1].split("/", 1)[0]
    if "groq" in host:
        return "Groq"
    if "cerebras" in host:
        return "Cerebras"
    if "openrouter" in host:
        return "OpenRouter"
    if "mistral" in host:
        return "Mistral"
    if host.startswith("localhost") or host.startswith("127.0.0.1"):
        return "Local"
    return host
