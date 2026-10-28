# ADR-004 — UUIDv7 identifiers and keyset pagination on (updated_at, id)

- **Status:** Accepted
- **Date:** 2026-10-28
- **Deciders:** Renan Silva (with AI assistant)
- **Related:** ADR-002

## Context

The spec requires a sidebar ordered "newest/recently updated first" with cursor
pagination, and separate deletions of conversations. It never chose an
identifier type, an ordering key, or a cursor format. Getting this wrong
produces the classic symptom: a conversation silently vanishes from the sidebar
or appears twice while pages are loading.

ID choice interacts with pagination, so both are decided here.

## Decision

- **Identifiers:** UUIDv7 for `conversations`, `messages`, and
  `generation_attempts`. Time-ordered, index-friendly, non-enumerable, and safe
  to expose in URLs. Generated in the application (Python), not by the database.
- **Conversation ordering key:** `(updated_at DESC, id DESC)`. `updated_at` is
  bumped inside the same transaction that inserts a message. `id` is the
  tiebreaker, which is what makes the order total and therefore cursor-safe.
- **Message ordering:** `seq`, an integer per conversation with a unique
  constraint. It is display order and is never renumbered.
- **Cursor:** opaque, `base64url(f"{updated_at.isoformat()}|{id}")`. Keyset
  predicate: `(updated_at, id) < (cursor_updated_at, cursor_id)` under the same
  `ORDER BY`. Invalid or undecodable cursors return `400 invalid_cursor`.
- **Page size:** default 20, maximum 20 in the MVP. The response includes
  `next_cursor` (null on the last page).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| `BIGINT` identity ids | Simplest cursors, but leaks row counts and global creation order, and makes records trivially enumerable in a project that will later grow multi-user concerns. |
| Random UUIDv4 | No index locality for the primary ordering path, and a separate sort key is needed anyway. |
| Offset pagination (`LIMIT/OFFSET`) | Skips and duplicates rows when new conversations arrive between page loads — the exact bug this ADR exists to prevent. It also degrades with table growth. |
| Order by `created_at` only | "Recently updated" is the required behaviour; a conversation continued today must rise in the list. |
| Order by the newest message's `created_at` (join) | Extra join on every page, and `updated_at` already carries the same information with simpler semantics. |
| `updated_at` only, no tiebreaker | Two conversations touched in the same microsecond produce a non-total order; cursors then drop or repeat rows. |

## Consequences

**Positive**

- Stable pagination under concurrent inserts and deletes.
- `ORDER BY updated_at DESC, id DESC` is served by a single composite index.
- No schema change needed to move to multi-user later; ids are already opaque.

**Negative / accepted costs**

- UUIDs are 16 bytes versus 8, and Python generation must use a library that
  supports v7 (`uuid_utils`, or `uuid6`/stdlib fallback with a documented
  monotonic workaround). This is one dependency with a clear justification.
- Cursors embed a timestamp, so they are decodable by anyone who has them. They
  are not secrets, only position markers.
- Retrying a message bumps `updated_at`, moving that conversation to the top of
  the sidebar. This is intentional: activity is what the ordering represents.

## Notes for implementation

- Use `timestamptz` with microsecond precision. If two rows can share a
  timestamp, the `id` tiebreaker keeps ordering deterministic.
- Do not bump `updated_at` on attempt status changes that produce no message;
  only message insertion bumps it.
- The cursor must be signed? No — it carries no authorization meaning in a
  single-user app. Revisit if authentication arrives.
