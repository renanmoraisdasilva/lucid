# ADR-007 — A second provider (OpenAI-compatible) and per-request model selection

- **Status:** Accepted
- **Date:** 2026-10-29
- **Deciders:** Renan Silva (with AI assistant)
- **Related:** ADR-001, ADR-003, ADR-005

## Context

ADR-001 chose Gemini as the only provider. In practice the free tier allows **20
requests per day** for `gemini-3.6-flash`. That is enough to demonstrate the
application once and not enough to use it, which turns every experiment into a
quota negotiation. The failure mode is also awkward to show: a 429 with an 11-hour
wait, surfaced to the user as a countdown.

The provider boundary from ADR-003 was built for exactly this moment: a `ChatProvider`
protocol with no SDK types in its signature, so a second adapter is a module, not a
refactor. Once a second provider exists, "which model?" becomes a user-visible
question, and the plan already listed a model picker as the deferred follow-up to
ADR-001.

Constraints discovered while verifying the endpoint:

- Groq's free plan allows **1,000 requests/day, 30 requests/minute, 8K tokens/minute
  and 200K tokens/day**. The tokens-per-minute ceiling is the binding one, not the
  daily count.
- `llama-3.3-70b-versatile` is listed on the account but is **not** available on the
  free plan (Enterprise / contact sales). The models that are free and currently
  listed are `openai/gpt-oss-120b`, `openai/gpt-oss-20b` and `qwen/qwen3.8-27b`.
- Groq speaks the OpenAI chat-completions shape, streamed as SSE, with usage in a
  final chunk. So do Cerebras, OpenRouter, Mistral and Ollama.

## Decision

### 1. One generic OpenAI-compatible adapter, not a Groq adapter

`providers/openai_compatible.py` implements `ChatProvider` against
`POST {OPENAI_BASE_URL}/chat/completions` with `stream: true` and
`stream_options.include_usage`. The base URL, key, timeout and default model are
configuration. Groq is the default endpoint; no Groq-specific code exists.

### 2. The compatible endpoint becomes the default provider, Gemini stays

`PROVIDER` defaults to `openai_compatible`. `PROVIDER=gemini` and `PROVIDER=fake`
remain supported. The key is read from `OPENAI_API_KEY` or `GROQ_API_KEY`
(`AliasChoices`), so either name works in an environment.

### 3. The catalogue is built from what is configured

`api/models.py` plus `application/models.py` expose `GET /api/models`:

```json
{
  "items": [{"id": "openai:openai/gpt-oss-120b", "label": "openai/gpt-oss-120b · Groq",
             "provider": "openai_compatible", "model": "openai/gpt-oss-120b"}],
  "default_id": "openai:openai/gpt-oss-120b"
}
```

An option exists only when its provider has a key, because offering a model that
fails on first use is worse than offering fewer models. With no key at all the
catalogue falls back to the scripted provider instead of failing startup, so a fresh
clone still boots and the UI still works.

### 4. Model is chosen per request, not per deployment

`POST /api/chat` and the retry endpoint accept an optional `model_id`. A missing id
means the catalogue default; an unknown id is `400 model_not_available` before any
message is persisted. The resolved model is stored on the attempt, so history stays
truthful when the selection changes later. Retry uses whatever is selected now,
which is how "that model failed, try another" works without a second endpoint.

### 5. One provider instance per provider, cached

`ProviderRegistry` builds each provider lazily, caches one instance, and is closed on
shutdown. Tests override a provider by name.

### 6. Smaller default context budget

`CONTEXT_MAX_INPUT_TOKENS` drops from 20,000 to 6,000. Under an 8K tokens/minute
ceiling, a 20K-token prompt would fail on the first call; 6,000 input plus a 2,048
output cap fits one request inside the minute. The budget was always configuration,
so this is a default change, not a design change.

### 7. Config renames keep working

`gemini_timeout_seconds` and `gemini_max_output_tokens` become
`generation_timeout_seconds` and `generation_max_output_tokens`, since neither was
ever Gemini-specific. Both spellings are accepted (`GENERATION_*` preferred,
`GEMINI_*` as an alias), so existing `.env` files do not break.

### 8. The picker is one control, and it is remembered

The composer renders a `<select>` bound to the catalogue, disabled while a response
streams, with the choice persisted in `localStorage`. The first load uses the
server's `default_id`, so the browser never disagrees with the backend about
defaults.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| A Groq-specific adapter | Duplicates the same wire format behind a vendor name, and the next provider would duplicate it again. The base URL is the only thing that differs. |
| Bundle a provider SDK (`openai`, `groq`) | A second SDK dependency and a second exception hierarchy to translate for a wire format that is a dozen lines of SSE parsing over the `httpx` client we already have. It also hides the streaming behaviour this project exists to teach. |
| Keep one model per deployment, switch by editing `.env` | Solves quota exhaustion by restarting the server, which is not a user-facing solution and teaches nothing about model selection. |
| Model id as a free-text field | Every typo becomes a provider error at generation time instead of a 400 at validation time, and the UI cannot show what is actually available. |
| Query `/models` from the provider at request time | Adds a network dependency and a cache-invalidation question to every page load; the account's model list is not the same as the models we chose to support. |
| Per-model rate-limit cooldowns | Correct in the long run, but the cooldown is a short-lived guard against hammering a provider that just said 429. One cooldown per process is honest and simple; a per-model key is a follow-up if the noise becomes real. |
| Provider fallback on failure (try Gemini when Groq 429s) | Explicitly out of scope in the spec (no fallback providers). The picker gives the user the same capability with an explicit choice instead of a silent substitution. |

## Consequences

**Positive**

- The application is usable on a normal day: 1,000 requests and 8K tokens/minute
  instead of 20 requests total.
- The provider boundary is now proven by use, not by assertion: a second adapter
  landed without touching the streaming, persistence, retry, or UI layers.
- Model selection is data, not code. Adding a model is an `.env` change
  (`OPENAI_MODELS`), and adding a provider is one adapter plus a registry entry.
- Tests stay offline: the fake provider is still the default in tests, and the
  catalogue has a deterministic single option there.

**Negative / accepted costs**

- Groq's tokens-per-minute limit means long conversations truncate sooner than they
  did on Gemini. The context budget keeps the request legal; it does not make it
  bigger.
- The cooldown is per process, not per model, so a 429 on one model briefly blocks
  the others too. Short wait, single-user app, documented rather than engineered
  around.
- The catalogue is a startup snapshot of configuration. If a model is retired
  upstream, the picker keeps offering it until the configuration changes and the
  first call fails.
- Accuracy now depends on `OPENAI_MODELS` being real: the free/paid distinction is
  not visible from `/models` alone, which is how `llama-3.3-70b-versatile` was
  initially assumed to work.
- Two providers means two sets of failure codes to keep mapped to one domain error
  taxonomy (ADR-005). The adapter tests cover the mapping; the taxonomy did not
  change.

## Follow-ups

- If a second concurrent user ever exists, revisit cooldown keying (provider or
  model) and the in-process registry assumption from ADR-003.
- The picker shows labels only; a per-model description (context window, price,
  rate limits) would need a richer catalogue than configuration strings.
