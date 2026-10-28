# ADR-002 — Assistant content is canonical on the message; attempts hold metadata

- **Status:** Accepted
- **Date:** 2026-10-28
- **Deciders:** Renan Silva (with AI assistant)
- **Related:** ADR-003, ADR-005

## Context

The spec defines three entities: `Conversation`, `Message`, and
`GenerationAttempt`. It left one question open: does generated assistant text
live on the message row, on the attempt row, or both?

The forces:

- A conversation view must render the transcript cheaply and deterministically.
- Failed attempts must not pollute the transcript, while interrupted attempts
  with partial text must remain visible.
- Retry creates additional attempts for the same user message, each potentially
  producing its own assistant text.
- Duplicating the same text in two tables guarantees drift and makes deletion
  and retention ambiguous.

## Decision

`messages.content` is the **single canonical** store of transcript text.
`generation_attempts` stores lifecycle, provider/model, timings, usage, and
sanitized error metadata, plus `assistant_message_id` pointing at the message it
produced (nullable when no assistant text exists).

Invariants enforced in the database:

- `messages`: `UNIQUE (conversation_id, seq)` and `role IN ('user','assistant')`.
- `generation_attempts`: `UNIQUE (user_message_id, attempt_no)`.
- `generation_attempts`: **partial unique index on `(conversation_id) WHERE
  status = 'in_progress'`** — at most one active generation per conversation,
  enforced by PostgreSQL rather than by application code alone.
- Cascading deletes from `conversations` to `messages` and
  `generation_attempts`; `assistant_message_id` is `ON DELETE SET NULL`.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Attempt owns the content; messages are thin pointers | Every transcript read becomes a join, the `message` concept loses its meaning, and user messages and assistant messages end up modelled differently for no gain. |
| Attempt owns content, copied into the message on success | Two sources of truth. The spec explicitly warns against it; it also makes "which copy is current" a real question during retries. |
| Store attempts only, no assistant message rows | Interrupted partials and completed responses would need different read paths from user messages, and pagination/ordering would get subtle. |

## Consequences

**Positive**

- One query renders a conversation; no content reconciliation logic.
- Failed attempts are invisible by construction (no message row), while
  interrupted attempts with partial text are visible (message row exists,
  attempt status is `interrupted`).
- The partial unique index turns the "one active generation" rule into a
  database guarantee, which also protects the startup-reconciliation path.

**Negative / accepted costs**

- An `in_progress` attempt has no assistant message yet, so the UI needs attempt
  state, not just messages, to show "generating". The API returns an
  `active_attempt_id` on the conversation for this reason.
- Attempt rows are meaningless without their messages; deletion must rely on
  cascades rather than manual ordering.

## Related decisions

- Partial text is buffered in memory and written once at terminal state (ADR-003).
- `interrupted` is reserved for stop/refresh/disconnect; post-token provider
  failures are `failed` (ADR-005).
