# Lucid Dashboard — Functional Specification

**Status:** Draft for implementation  
**Product:** Lucid, a single-user AI chatbot  
**Scope:** Learning-focused usage and application observability dashboard

## 1. Purpose

The Lucid dashboard gives the user visibility into how the chatbot behaves and how the underlying LLM is used. It serves two purposes:

1. **Application observability:** understand whether generations succeed, fail, or are interrupted, and inspect latency and retry behavior.
2. **LLM learning:** understand token consumption, model usage, and estimated API spend.

The dashboard should remain a focused, lightweight feature—not a full observability platform.

## 2. Product context and constraints

- Lucid is a single-user application. Authentication and multi-user analytics are outside this scope.
- The chatbot uses a backend-configured Gemini model.
- Conversation history is persisted separately from telemetry.
- Telemetry retention must never delete or shorten conversation history.
- PostgreSQL is the initial storage system; no analytics warehouse is required.
- The dashboard is a separate page reached from the main sidebar.
- The dashboard is read-only.
- Do not store full prompts, message bodies, or raw provider request/response payloads as telemetry.

## 3. Navigation and page behavior

- Add a **Dashboard** navigation item to the main sidebar.
- Selecting it opens a dedicated dashboard page, separate from the chat interface.
- Default date range: **last 7 days**.
- Provide quick date-range choices: last 24 hours, last 7 days, and last 30 days.
- Include a manual refresh action.
- Refresh automatically every **15–30 seconds**.
- Use ordinary request/response calls; do not introduce WebSockets or SSE solely for dashboard updates.
- Show the selected date range and the time of the most recent successful refresh.
- Handle loading, empty, and error states. A refresh failure should not erase already displayed data; indicate that the data may be stale.

## 4. Dashboard content

### 4.1 Overview metrics

Show aggregate metrics for the selected date range:

- Conversation count
- User message count
- Generation attempt count
- Generation success rate
- Total input tokens
- Total output tokens
- Estimated API cost

A **generation attempt** is one user-visible attempt, stored once in
`generation_attempts`. A manual Retry creates a new attempt; the bounded
automatic retries defined in ADR-005 happen inside the attempt and are reflected
by a retry count, not by extra rows. Calculate success rate using completed,
failed, and interrupted attempts as the denominator; exclude attempts that have
not reached a terminal state.

### 4.2 Trends

Show time-series charts for:
- Token usage over time (input and output)
- Generation latency over time
- Reliability over time (successes, failures, and interruptions)

Choose sensible time buckets for the selected date range. Represent empty or sparse periods honestly; do not imply more precision than the data supports.

### 4.3 Latency

Track:
- **Time to first token (TTFT):** elapsed time from initiating the generation request until the first streamed response token/chunk is received.
- **Total generation duration:** elapsed time from initiating the attempt until it reaches a terminal state.

Show aggregate latency values for the selected period. Median and p95 may be shown when the sample is sufficient; otherwise show the sample count or an unavailable state.

### 4.4 Token usage

Show:
- Total input tokens
- Total output tokens
- Average input tokens per generation
- Average output tokens per generation

Use provider-reported token usage when available. If usage is unavailable for an attempt, do not fabricate a value. Indicate when totals are partial because some attempts did not return usage data.

The initial version does not need to split input tokens into system prompt, conversation history, and current user message. Cached-token analytics and per-conversation token growth are also out of scope.

### 4.5 Estimated API cost

Show one estimated API cost total for the selected date range.

- Calculate the estimate from available input/output token usage and the configured model's pricing.
- Keep model pricing configurable and maintainable; do not scatter hardcoded rates through application code.
- Label the value clearly as an **estimate**, not actual billing.
- If token usage or pricing is unavailable, show the estimate as unavailable or partial rather than guessing.
- No daily cost chart, per-conversation cost, or input/output cost breakdown in the initial version.

## 5. Generation tracking

Record one telemetry record per generation attempt, including manual retries.
Automatic retries are counted on the attempt (`retry_count`), not recorded as
separate attempts; regeneration is out of scope for the MVP.

### 5.1 Required fields

Capture at minimum:

- Generation attempt identifier
- Associated conversation identifier
- Model identifier/name
- Start timestamp
- First-token timestamp, when a token is received
- Terminal timestamp, when the attempt completes, fails, or is interrupted
- Terminal status: `completed`, `failed`, or `interrupted`
- Total duration
- TTFT, when available
- Input token count, when available
- Output token count, when available
- Retry count or retry-attempt relationship
- HTTP status, when available
- Error category and safe, concise error detail, when applicable
- Context size sent to the provider, when it can be measured reliably

Do not assume the provider exposes every field. Persist unavailable values as null and reflect missing data honestly in the dashboard.

**Storage (confirmed 2026-10-29):** the fields that the original model does not
carry map to four nullable columns on `generation_attempts`: `first_token_at`,
`http_status`, `retry_count` (automatic retries inside the attempt), and
`context_tokens`. Total duration is derived from `started_at` and `completed_at`.
Rows written before the migration keep null and render as unavailable.

### 5.2 Attempt lifecycle

- Create the attempt record when model generation begins.
- Record the first-token timestamp when the first streamed response content arrives.
- Mark the attempt `completed` when generation finishes normally.
- Mark it `failed` when generation terminates due to an error.
- Mark it `interrupted` when generation is stopped or otherwise intentionally cut short.
- Prevent attempts from remaining indefinitely in a non-terminal state after a process-level failure; use a safe reconciliation or timeout strategy.
- Manual retries must be distinguishable from the original attempt (`attempt_no`).
  Do not collapse multiple manual attempts into one record. Automatic retries
  inside an attempt are visible through `retry_count`.
- A partial assistant response may be preserved according to chat behavior, but telemetry must accurately reflect that the generation was interrupted or failed.

### 5.3 Privacy and diagnostics

- Do not store full prompts, conversation messages, or raw provider request/response payloads in telemetry.
- Generation details in the dashboard show metadata only.
- Sanitize error details to avoid exposing secrets, credentials, or sensitive content.
- Do not add a raw diagnostics viewer or per-chunk lifecycle event timeline in the initial version.

## 6. Recent Generations

Include a table of recent attempts with:

- Timestamp
- Conversation reference
- Status
- Model
- Input tokens
- Output tokens
- TTFT
- Total duration
- Retry information

Selecting a row opens a **compact details** view containing status, model, input/output token counts, TTFT, total duration, and error details when relevant.

Do not include raw request/response payloads, full prompt content, or a detailed event timeline.

**Display limit:** the latest **25** attempts. Confirmed during the mockup review
on 2026-10-29; pagination remains deferred.

## 7. Telemetry retention and cleanup

- Retain detailed generation telemetry for **30 days**.
- Automatically delete expired telemetry records after the retention period.
- Do not delete conversations or chat messages as part of telemetry cleanup.
- Ensure cleanup respects relationships and does not leave invalid references.
- Retention applies to telemetry and generation-detail records, not conversation history.
- After telemetry cleanup, the transcript keeps its message content, but the attempt-derived
  usage badge and completed/failed/interrupted marker are no longer available. This is
  accepted: retention removes telemetry, not conversation history.

## 8. Error, loading, and empty states

Handle:
- Initial loading
- No telemetry in the selected date range
- Partial metrics when provider usage data is missing
- Dashboard request failure
- Automatic refresh failure
- Missing model pricing
- Insufficient samples for latency percentiles

Use clear explanations rather than displaying misleading zeroes when a value is unknown or unavailable.

## 9. Out of scope for the initial version

- Multi-user analytics, authentication, teams, or workspaces
- Advanced filters by model, conversation, status, or error category
- Per-conversation analytics
- Input-token breakdown by system prompt, history, and current message
- Cached-token analytics
- Daily or per-conversation cost breakdown
- Raw provider payload inspection
- Per-chunk timing and detailed streaming event timelines
- Analytics export
- Analytics warehouse or external observability service
- WebSockets/SSE for dashboard refresh
- Model selection or model configuration controls on the dashboard

## 10. Suggested implementation approach

Keep implementation aligned with Lucid's existing stack and architecture:

1. Add a generation-attempt telemetry model and database migration.
2. Instrument the backend generation lifecycle, including streaming, retries, completion, failure, and interruption.
3. Persist provider usage metadata when available.
4. Add retention cleanup for telemetry older than 30 days.
5. Add read-only dashboard API endpoints that aggregate metrics by date range.
6. Build the dashboard page and sidebar navigation in React.
7. Add periodic refresh and manual refresh.
8. Test aggregation boundaries, missing usage/pricing, retries, interrupted streams, cleanup, and empty/error states.

Prefer simple SQL aggregation in PostgreSQL for the initial single-user workload. Avoid introducing separate analytics infrastructure.

## 11. Acceptance criteria

- The user can open Dashboard from the main sidebar.
- The dashboard defaults to the last 7 days and supports 24-hour, 7-day, and 30-day ranges.
- Data refreshes every 15–30 seconds and can be refreshed manually.
- The overview shows conversation count, user message count, generation attempts, success rate, input/output token totals, and estimated API cost.
- Trend charts show token usage, latency, and reliability over time.
- Generation attempts are tracked separately, including retries and regeneration attempts.
- Each attempt records the lifecycle metadata listed above when available.
- The user can inspect compact details for a recent generation attempt.
- Missing token usage or pricing is represented as unavailable/partial, never fabricated.
- Telemetry older than 30 days is automatically cleaned up without deleting conversation history.
- No full prompts, message bodies, or raw provider payloads are stored in telemetry.
- The dashboard remains useful when there is no data or provider metadata is unavailable.

## 12. Mockup review decisions (2026-10-29)

Confirmed after reviewing `../screen-mockups/dashboard.html` against this spec and
ADR-005. The mockup was rewritten to match these decisions.

| # | Decision | Outcome |
|---|---|---|
| 1 | Visual language | Reuse `theme.js` tokens and `shell.js` chrome; the dashboard is not a second design system. |
| 2 | Navigation | A **Dashboard** row in the shared sidebar above the conversation groups. No mobile bottom bar; mobile keeps the off-canvas sidebar. |
| 3 | Section scope | Overview metrics, trends (tokens, TTFT, duration, reliability), token usage and one cost estimate, recent 25 attempts with compact details. Context-budget/compaction, throughput histogram, cost-per-run, cached tokens, export, model picker, search/filter, and a trace viewer are removed. |
| 4 | Overview metrics | All seven metrics in one row: conversations, user messages, attempts, success rate, input tokens, output tokens, estimated cost. |
| 5 | Conversation count | Conversations with at least one message in the range, with a "new in range" sublabel. |
| 6 | Comparisons | No "vs previous period" deltas in the initial version. |
| 7 | Attempt semantics | Automatic retries stay inside one attempt row and are shown as a count; manual Retry creates a new row. Matches ADR-005. |
| 8 | New columns | `first_token_at`, `http_status`, `retry_count`, `context_tokens`, all nullable. |
| 9 | Recent generations | Time, conversation reference, status, model, input/output tokens, TTFT, duration, attempt. No attempt id or trace action. |
| 10 | Details view | A compact modal, same pattern as the delete-conversation dialog. |
| 11 | Status labels | `Completed`, `Failed`, `Interrupted`; interrupted keeps the amber marker. |
| 12 | Cost | Estimated at configured list price, labelled as an estimate, with an explicit note that the free tier bills nothing. |
| 13 | Latency charts | Median and p95 for TTFT and total duration; p95 only where a bucket has at least 20 attempts, otherwise the sample count is shown. |
| 14 | Buckets | Hourly for 24 hours, daily for 7 and 30 days. |
| 15 | Refresh | Every 20 seconds, paused while the tab is hidden, plus a manual refresh action. A failed refresh keeps the last good data and marks it stale. |
| 16 | States | Dedicated empty, loading, stale-refresh, request-failure, partial-usage, thin-sample, and missing-pricing presentations. |

The Recent Generations limit is now **25** and is no longer an open detail.
