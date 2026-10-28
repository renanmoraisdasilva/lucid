# ADR-005 — Failure semantics, retry policy, and crash reconciliation

- **Status:** Accepted
- **Date:** 2026-10-28
- **Deciders:** Renan Silva (with AI assistant)
- **Related:** ADR-002, ADR-003

## Context

The spec requires "Robust" failure handling and distinguishes `completed`,
`failed`, and `interrupted` attempts, but leaves open: which errors are
retryable, how many retries, what happens when the provider fails after text has
already streamed, and what to do with attempts stranded by a crash.

Two failure shapes must be handled, not one:

- **HTTP-level failures** on the provider call (429, 5xx, timeouts, connection
  errors).
- **Mid-stream `error` events** on an already-200 SSE response, carrying a
  provider code such as `gateway_timeout`.

## Decision

### Status semantics

| Status | Meaning |
|---|---|
| `completed` | Provider finished; assistant message persisted |
| `failed` | Provider/system error ended the attempt. If text had already streamed, that message stays visible with a failed marker; otherwise no assistant message exists |
| `interrupted` | The user stopped, refreshed, or disconnected. Partial text, if any, stays visible |

### Retry policy

- Maximum **2 automatic retries** after the initial attempt (3 provider calls
  worst case).
- Exponential backoff from **1s**, doubling, capped at **8s**, with jitter.
  Jitter must be injectable/disabled in tests.
- Retryable: connection errors, timeouts, HTTP `429`, `500`, `502`, `503`, `504`,
  and provider stream codes `gateway_timeout` / `unavailable` / `overloaded`.
- Not retryable: `400`, `401`, `403`, `404`, validation failures, safety blocks,
  `context_too_large`, and anything arriving **after the first text delta has
  been produced** for that attempt.
- Automatic retries happen inside a single attempt, so they do not create extra
  attempt rows.
- The **manual Retry** action always operates on the existing user message: it
  creates a new attempt (`attempt_no + 1`), never a new user message, and is
  rejected with `409 generation_already_completed` when a completed attempt
  already exists for that message.

### Concurrency

A message submitted while a generation is active is rejected with
`409 generation_in_progress` and the active `attempt_id` in `details`, so a
refreshed client can recover its state instead of guessing.

### Crash reconciliation

On application startup, before serving traffic:

```sql
UPDATE generation_attempts
   SET status = 'interrupted', error_code = 'process_restart', completed_at = now()
 WHERE status = 'in_progress';
```

Because partial text is written only at terminal state, a crashed attempt has no
assistant message; the user sees the error/Retry affordance and loses only the
unpersisted tail.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| No automatic retries | Misses the most common free-tier failure (429) and does not meet the spec's "Robust" requirement. |
| 3+ retries with a 30s cap | Holds the UI hostage on a hard-down provider and multiplies quota use; the user has a manual Retry button. |
| Treat post-token failures as `interrupted` | Hides genuine provider faults, corrupts monitoring, and makes "did the user stop this?" unanswerable. |
| Discard partial text on failure | Throws away output the user has already read, and the spec requires preserving received text on interruption. |
| Retry by inserting a new user message | Duplicates the user's message and breaks the retry contract in the spec. |
| Persist an assistant row for every failed attempt as a placeholder | Pollutes the transcript with rows that have no content, and complicates ordering and `seq` semantics. |
| Reconcile stranded attempts lazily on read | Spreads the correction across every read path and leaves conversations blocked until someone looks at them. |

## Consequences

**Positive**

- Partial output is never destroyed, and the user always has a next action.
- Retry accounting is exact: N attempts, one user message.
- `interrupted` and `failed` carry distinct, testable meanings that map to
  visible UI states.

**Negative / accepted costs**

- The 409 concurrency rule means a stale tab can block a conversation until its
  attempt is cancelled; the stop endpoint is idempotent so the UI can clear it.
- The retry matrix needs real tests (eligibility table, backoff bounds, no retry
  after first token) rather than a happy-path check.
- Auto-retry inside one attempt hides transient blips from the transcript, which
  is intended, but attempt metadata will not show how many calls occurred unless
  the adapter logs them. Log each provider call with the attempt id.

## Follow-ups

- If retry behaviour changes (circuit breaker, provider fallback), record a new
  ADR. Explicitly out of MVP scope.
