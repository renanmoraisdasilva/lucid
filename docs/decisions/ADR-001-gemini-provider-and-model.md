# ADR-001 — Gemini provider integration: Interactions API, stateless requests

- **Status:** Accepted
- **Date:** 2026-10-28
- **Deciders:** Renan Silva (with AI assistant)
- **Supersedes:** none

## Context

The MVP needs one hosted LLM provider, chosen for free-tier operation and for
learning a native provider API rather than a framework. Google currently
recommends the **Interactions API** for new projects — it is GA since June 2026,
is where new models and capabilities launch, and its predecessor
`generateContent` is documented as legacy (though still supported).

The Interactions API offers optional server-side conversation state
(`store=true` by default, chaining turns with `previous_interaction_id`). The
specification requires the application to own conversation persistence and to
send only a bounded, budgeted slice of history to the model.

Two facts from the current documentation constrain the design:

1. `store=false` is incompatible with background execution, and `cancel(id)`
   only applies to background interactions.
2. Streaming errors can arrive mid-stream as an `error` event with a provider
   code (for example `gateway_timeout`), not only as an HTTP status.

## Decision

1. Integrate Gemini through the **Interactions API** using the `google-genai`
   Python SDK, version `>= 2.3.0` (first version exposing Interactions).
2. Send every request **statelessly**: `store=false`, no
   `previous_interaction_id`, full bounded history supplied by the application.
3. Use **`gemini-3.5-flash-lite`** as the initial model, configured exclusively
   through environment configuration (`GEMINI_MODEL`), never hard-coded in the
   adapter.
4. Keep the entire provider surface behind one adapter module. Only
   `providers/gemini.py` may import `google.genai`.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| `generateContent` API | Legacy; new models and features launch on Interactions. Lower learning value for the next projects in the roadmap. |
| Interactions API with `previous_interaction_id` state | Provider-side history cannot be bounded by our context budget, expires after 1 day on the free tier, and couples conversation durability to a Google-side record. It also undermines the provider boundary that later projects depend on. |
| Raw REST over HTTPX | Maximum wire-level learning, maximum work: we would own SSE parsing, retry semantics, and error mapping for no benefit over an isolated SDK adapter. |
| Background execution + `cancel(id)` | Forces `store=true`, converts a stream into a job-polling system, and is unnecessary for turn-length generations. |

## Consequences

**Positive**

- Google's recommended, forward-looking surface; the adapter will not need a
  migration to keep receiving new model support.
- Context budgeting stays entirely in application code, which is the point of
  the exercise, and the provider boundary stays honest enough for a second
  adapter in a later project.
- Nothing is retained on Google's side beyond the request itself.

**Negative / accepted costs**

- We resend history every turn, so input tokens (and cost on a paid tier) are
  higher than a stateful setup would allow. Acceptable on the free tier and
  bounded by the context budget.
- Cancellation is client-side only. After a stop, the provider may finish the
  generation server-side. This is documented behaviour, not a defect.
- We ignore `thought`, `thought_signature`, and tool steps. Thinking tokens are
  still reported in usage and are stored, but never rendered.
- The Interactions API has already had one documented breaking-change round
  (May 2026), so the SDK version is pinned and the adapter is covered by
  contract tests against recorded fixtures.

## Amendment (2026-10-29): model changed to `gemini-3.6-flash`

**Context.** `gemini-3.5-flash-lite` was the original choice (decision 3 above) for
cost. Measurement showed the free tier queuing it for 30–66 seconds per call —
the delay occurred before `interaction.created`, so it was provider scheduling,
not generation. Interleaved calls in the same window: lite 38.5s / 42.1s / 32.6s
to first token, `gemini-3.6-flash` 2.2s / 14.6s.

**Decision.** Default `GEMINI_MODEL` to `gemini-3.6-flash`. It is still free-tier,
faster in every paired sample, and the model id remains configuration only.

**Consequences.** Slightly higher token cost on a paid tier; the churn risk in
R1 is unchanged and the model picker remains the post-MVP follow-up. The original
reasoning above is kept as history, not rewritten.

## Follow-ups

- **Model churn is a tracked risk.** See the risk section of
  `docs/plans/implementation-plan.md`. A model registry and/or user-facing model
  picker is explicitly deferred past the MVP.
- Re-verify the adapter spike (method names on the async client, `store`
  parameter placement, usage field names, mid-stream error payload) before
  Milestone 3 is considered done, and record findings in
  `docs/architecture/gemini-adapter-notes.md`.
