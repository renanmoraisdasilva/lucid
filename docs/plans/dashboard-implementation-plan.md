# Lucid dashboard — implementation plan

**Status:** Draft for implementation
**Spec:** [002 — Lucid Dashboard](../specs/002-lucid-dashboard-spec.md)
**Mockups:** [dashboard.html](../screen-mockups/dashboard.html), [dashboard-states.html](../screen-mockups/dashboard-states.html)
**Prerequisite:** [code health budget](./code-health-budget.md) and its hot-spot
refactor must be green before D1 starts.

## 1. Scope

A read-only dashboard reached from the sidebar: seven overview metrics, token and
latency trends, daily reliability, one estimated cost, and the latest 25
generation attempts with a compact details dialog.

Not in scope: filters, export, model controls, per-conversation analytics,
compaction/cache analytics, raw payloads, or a live event timeline. Spec 002 §9
is the authority.

## 2. Decisions taken

| # | Decision | Consequence |
|---|---|---|
| 1 | **One aggregate endpoint**, `GET /api/dashboard?range=7d` | One round trip per refresh; a failed refresh leaves the previous payload intact. The endpoint is small (~25 recent rows), so splitting it would add loading states without a benefit. |
| 2 | **24h is a rolling 24-hour window**; 7d and 30d are **calendar-day windows ending today (UTC)**; default `7d` | The chart has exactly 24, 7 or 30 buckets and today is partial for daily ranges. An invalid range returns the standard `422` envelope. |
| 3 | Buckets are **hourly for 24h, daily for 7/30d, in UTC** | The axis labels say UTC dates. Table timestamps are rendered in browser local time. Documented limitation; a per-user timezone is a later decision. |
| 4 | An attempt is a **user-visible attempt** | Manual retry creates a row (`attempt_no`); automatic retries increment `retry_count` inside the row, per ADR-005. |
| 5 | Overview counts are **terminal attempts started in the window** | In-progress attempts do not inflate the count or the success-rate denominator. If any exist, the response reports them separately and the UI ignores them. |
| 6 | Conversations = **distinct conversations with a message in the window**; "new" = created in the window | Matches the mockup's "18 active / 7 new" and reflects usage, not just new chats. |
| 7 | Usage is **provider-reported only** | Null input/output stays null. The response carries `usage_partial` when any terminal attempt has no usage. |
| 8 | Pricing is **configuration, no defaults in code** | Without configured rates the cost is `null` and the UI says unavailable. `.env.example` carries example list prices. |
| 9 | Telemetry is **buffered and written once at terminal state** | Same transaction as the assistant message. A crash keeps nulls and becomes `interrupted` via startup reconciliation. |
| 10 | Retention deletes **terminal attempts older than 30 days**, at startup and every 24h | Conversations and messages are untouched; `assistant_message_id` is `SET NULL` already. |
| 11 | Frontend uses an **app-level view switch**, not a router | No new dependency. The chat page stays mounted and hidden while the dashboard is open, so an in-flight stream is not aborted. |
| 12 | Charts are **hand-rolled SVG with HTML labels**, no chart library | Three chart families do not justify a dependency; the shared geometry lives in one tested module. |

## 3. Data model changes

Migration `0003_dashboard_telemetry.py`.

| Column | Type | Null | Notes |
|---|---|---|---|
| `first_token_at` | `timestamptz` | yes | first streamed text delta |
| `http_status` | `integer` | yes | provider response status, when known; check 100–599 |
| `retry_count` | `integer` | no, default 0 | automatic retries inside this attempt; check ≥ 0 |
| `context_tokens` | `integer` | yes | app estimate of the prompt sent; check ≥ 0 |

Indexes:

- `ix_attempts_started_at (started_at)` for range scans.
- `ix_messages_created_at (created_at)` for active-conversation and user-message
  counts.

Add a check `first_token_at IS NULL OR first_token_at >= started_at`. Do not add a
derived duration/TTFT column; compute both in SQL.

Migration tests cover upgrade from `0002`, downgrade/upgrade, constraints and the
two indexes.

## 4. Backend design

### 4.1 Instrumentation

- `application/context.py`: `select_history` returns a `ContextSelection` with the
  chosen messages and `estimated_tokens`; the budget logic and tests are unchanged.
- `application/chat/telemetry.py`: a mutable `AttemptTelemetry` holding
  `first_token_at`, `http_status`, `retry_count` and `context_tokens`. It is created
  at attempt start and passed to the stream helpers.
- `application/chat/events.py`: extract `meta`, `usage`, `done` and `error` payload
  construction from `streaming.py`. This keeps the streaming module under the
  250-line warning as telemetry is added.
- `application/chat/streaming.py`: set `first_token_at` on the first `TextDelta`,
  set `http_status` on completion or failure, and pass telemetry to the finalizer.
- `application/chat/retries.py`: increment `retry_count` on each automatic retry.
  It stays inside the same attempt row.
- `domain/errors.py` + `providers/gemini.py`: add `http_status` to `ProviderError`
  and translate the SDK status once. The fake provider returns `None`.
- `application/chat/finalize.py`: write all four telemetry fields with status,
  usage and the assistant message in the same terminal transaction.
- Cancellation/finalization writes the same fields; an interrupted attempt keeps
  its first-token timestamp.

### 4.2 Aggregation

`persistence/dashboard_queries.py` holds SQL only; `application/dashboard/`
orchestrates. No SQL in routes or React.

| Query | Output |
|---|---|
| Overview | conversations active/new, user messages, terminal attempts by status, success rate, token sums, attempts with usage, in-progress count |
| Buckets | per hour/day: attempts by status, token sums, TTFT/duration samples and percentiles |
| Period latency | `percentile_cont(0.5/0.95)` for TTFT and duration plus sample counts |
| Recent | latest 25 attempts joined to conversation title, ordered by `started_at DESC` |

Rules:

- Filter attempts by `started_at >= :start AND started_at < :end`, terminal only
  for metrics.
- TTFT = `(first_token_at - started_at)` in ms; duration =
  `(completed_at - started_at)` in ms.
- `percentile_cont` per bucket is returned only when the bucket has at least 20
  samples; the service sets p95 to null otherwise. Period percentiles use the same
  threshold.
- Buckets missing from SQL are filled by the service with `attempts: 0`, zero
  token sums and null latencies. A bucket with attempts but no usage gets `null`
  token sums, not a fabricated zero. The chart draws a gap for null values and a
  real zero only when no attempt happened.
- Empty denominators are null, not zero: `success_rate` is null when there are no
  terminal attempts; token totals are null when no attempt returned usage; cost is
  null when usage or pricing is unavailable.
- Partial usage: count terminal attempts with a null input or output token. A
  non-null total with at least one missing sample carries `partial: true`. Averages
  divide by attempts that actually returned usage.
- A completed stream records `http_status = 200`; a failure records the status
  carried by `ProviderError` (null when the fake provider or a mid-stream error
  gives none).

### 4.3 Pricing and retention

`application/dashboard/pricing.py`:

```
rate_in = Decimal(str(settings.pricing_input_usd_per_million))
rate_out = Decimal(str(settings.pricing_output_usd_per_million))
cost = (input_tokens / 1_000_000) * rate_in + (output_tokens / 1_000_000) * rate_out
```

Settings additions:

- `pricing_input_usd_per_million: float | None = None`
- `pricing_output_usd_per_million: float | None = None`
- `pricing_free_tier: bool = True`

Missing rates produce `estimated_cost_usd: null` and `pricing_available: false`.
Example values in `.env.example` are labelled as placeholders, not billing data.

`application/dashboard/retention.py`: delete terminal attempts older than 30 days.
Run once during lifespan startup (after reconciliation) and then on a 24-hour
asyncio task; cancel on shutdown. Log the deleted count, never message content.

**Retention consequence:** the chat read model derives a message's usage badge,
interrupted/failed marker and retryability from its attempt. Once the attempt is
deleted, the message content remains but those metadata disappear. That is the
accepted meaning of "telemetry retention" in spec 002 §7; if historical status
must survive, copy a status/usage snapshot onto the message in a separate schema
decision. The integration test asserts that messages and conversations survive
retention.

### 4.4 API

`GET /api/dashboard?range=7d` → `200 application/json`.

```
{
  "range": "7d",
  "generated_at": "2026-10-29T13:00:00Z",
  "overview": {
    "conversations_active": 18,
    "conversations_new": 7,
    "user_messages": 121,
    "attempts": 138,
    "completed": 128,
    "failed": 5,
    "interrupted": 5,
    "in_progress": 0,
    "success_rate": 0.928,
    "input_tokens": 283100,
    "output_tokens": 83300,
    "average_input_tokens": 2097,
    "average_output_tokens": 617,
    "usage_partial": true,
    "estimated_cost_usd": 0.29,
    "pricing": {
      "available": true,
      "free_tier": true,
      "input_usd_per_million": 0.3,
      "output_usd_per_million": 2.5
    }
  },
  "bucket": "day",
  "trend": [
    {
      "bucket_start": "2026-10-23T00:00:00Z",
      "attempts": 22,
      "completed": 20,
      "failed": 1,
      "interrupted": 1,
      "input_tokens": 55400,
      "output_tokens": 16800,
      "ttft_ms_p50": 430,
      "ttft_ms_p95": 760,
      "duration_ms_p50": 2200,
      "duration_ms_p95": 4800
    }
  ],
  "latency": {
    "ttft": { "p50_ms": 483, "p95_ms": 1040, "samples": 133 },
    "duration": { "p50_ms": 2600, "p95_ms": 5700, "samples": 138 }
  },
  "recent": [
    {
      "attempt_id": "uuid",
      "started_at": "2026-10-29T13:40:56Z",
      "conversation_id": "uuid",
      "conversation_title": "Event-Driven Architecture & Bus",
      "status": "completed",
      "model": "gemini-3.6-flash",
      "attempt_no": 1,
      "retry_count": 0,
      "input_tokens": 8412,
      "output_tokens": 1284,
      "ttft_ms": 486,
      "duration_ms": 2600,
      "http_status": 200,
      "context_tokens": 8412,
      "error_code": null,
      "error_message": null
    }
  ]
}
```

`recent` never contains message content or prompts. Error messages are the
sanitized values already stored on the attempt. Before exposing them, audit the
adapter's strings for provider URLs, request ids or credentials; if a value cannot
be guaranteed safe, return `error_code` only and leave `error_message` null. A test
asserts that the response has no `content`/`prompt` fields and no URL-like error
detail.

## 5. Frontend design

### 5.1 Shell and navigation

- `App.tsx` owns `view: "chat" | "dashboard"` and the `useChat()` controller.
- The sidebar is rendered once in `App.tsx` and receives `activeView` and
  `onDashboard`.
- `pages/ChatPage.tsx` is the old `ChatWorkspace` without the sidebar.
- `pages/DashboardPage.tsx` renders its own header, toolbar and sections.
- `ChatPage` stays mounted with `hidden` while the dashboard is visible. The SSE
  request is not aborted by navigation. Selecting a conversation switches back to
  chat.
- Ctrl/⌘+K switches to chat and starts a new one.

### 5.2 Data and refresh

- `api/dashboard.ts`: typed `getDashboard(range, signal)` using the existing
  `requestJson` helper; export the error path.
- `hooks/useDashboard.ts`: `useQuery` with `refetchInterval: 20_000`,
  `refetchIntervalInBackground: false`, `retry: 1`, `staleTime: 0`. A range change
  unmounts/remounts the query (`queryKey` includes the range), so the page shows its
  loading skeleton instead of yesterday's numbers under a new range label. A
  background refetch keeps the current data by default.
- Manual refresh calls `refetch()`. A `useEffect` ticker updates "Updated Ns ago"
  from `dataUpdatedAt` every 5 seconds.
- Stale state: `error !== null && data !== undefined` shows the amber banner above
  the metrics; data is never removed. `error !== null && data === undefined` shows
  the full error panel. Do not rely on `isError` alone for background refetch
  failures; check the error object with the presence of data.
- Range is local state, default `7d`; no URL/router coupling in the MVP.

### 5.3 Charts

- `lib/chart.ts`: `scaleLinear`, `buildPath`, `buildArea`, `breaksForNulls`,
  `niceTicks`. Pure and unit-tested.
- `components/dashboard/ChartFrame.tsx`: HTML legend, y-axis labels and x-axis
  labels; the plot area contains an SVG with `viewBox="0 0 100 100"` and
  `preserveAspectRatio="none"` for geometry only. Lines use
  `vector-effect="non-scaling-stroke"` so they stay 1–2 px. No text inside the SVG,
  so the mobile scaling problem from the mockup does not return.
- One component per chart family: token trend (two series, area for input),
  latency (p50 solid, p95 dashed, gaps for nulls), reliability (stacked HTML bars,
  not SVG).
- Empty buckets render a real zero for tokens and a gap for latency. A tooltip is
  provided with `<title>` per point/bar; no chart library.

## 6. File inventory and size budget

Estimates are planning ceilings, not commitments. Revise once the API shape is
fixed at D3. The prerequisite refactor is separate and not counted here.

### Backend

| File | Purpose | Est. | Cap |
|---|---|---:|---:|
| `persistence/tables.py` (edit) | four columns, checks, indexes | +8 | exempt |
| `migrations/versions/0003_dashboard_telemetry.py` | schema + indexes | 60 | exempt |
| `application/context.py` (edit) | return selection + estimate | +15 | 250 |
| `application/chat/telemetry.py` | per-attempt capture (first token, status, retries, context) | 26 | 250 |
| `application/chat/events.py` | meta/usage/done/error payload construction | 75 | 250 |
| `application/chat/streaming.py` (edit) | use telemetry; events extracted | 242 | 300 |
| `application/chat/retries.py` (edit) | retry counter | +10 | 250 |
| `application/chat/finalize.py` (edit) | persist telemetry | +20 | 250 |
| `domain/errors.py` (edit) | `http_status` | +6 | 300 |
| `providers/gemini.py` (edit) | map provider status | +15 | 350 |
| `application/dashboard/service.py` | orchestration, partial flags | 194 | 300 |
| `application/dashboard/results.py` | final result types | 92 | 250 |
| `application/dashboard/query_rows.py` | raw query row types | 75 | 250 |
| `application/dashboard/buckets.py` | range → buckets | 49 | 250 |
| `application/dashboard/pricing.py` | estimate, availability | 56 | 250 |
| `application/dashboard/retention.py` | 30-day cleanup | 59 | 250 |
| `persistence/dashboard_queries.py` | overview SQL | 113 | 300 |
| `persistence/dashboard_sql.py` | shared SQL expressions | 53 | 300 |
| `persistence/dashboard_trend_queries.py` | trend and latency SQL | 108 | 300 |
| `persistence/dashboard_recent.py` | recent-attempts SQL | 67 | 300 |
| `api/routes_dashboard.py` | one GET endpoint | 129 | 300 |
| `api/schemas.py` (edit) | response models | +156 | 300 |
| `main.py` (edit) | retention lifespan task | +20 | 300 |
| `config.py` (edit) | pricing settings | +8 | 250 |

Backend source: ~1,100 lines. Tests:

| File | Est. |
|---|---:|
| `tests/unit/test_dashboard_buckets.py` | 120 |
| `tests/unit/test_dashboard_pricing.py` | 100 |
| `tests/unit/test_dashboard_partial.py` | 90 |
| `tests/integration/test_dashboard_queries.py` | 260 |
| `tests/integration/test_dashboard_api.py` | 180 |
| `tests/integration/test_telemetry_fields.py` | 160 |
| `tests/integration/test_retention.py` | 100 |
| `tests/integration/dashboard_support.py` | 70 |
| `tests/test_code_health.py` | 80 |

Backend tests: ~1,160 lines.

### Frontend

| File | Purpose | Est. | Cap |
|---|---|---:|---:|
| `src/App.tsx` (edit) | shell, view state, shared sidebar | 90 | 180 |
| `src/pages/ChatPage.tsx` | chat content without sidebar | 110 | 180 |
| `src/pages/DashboardPage.tsx` | layout, toolbar, states | 120 | 180 |
| `src/components/Sidebar.tsx` (edit) | Dashboard row, active view, off-canvas drawer | +40 | 200 |
| `src/components/SidebarToggle.tsx` | header menu button | 15 | 100 |
| `src/api/dashboard.ts` | fetch + types | 90 | 200 |
| `src/api/types.ts` (edit) | dashboard payload types | +90 | 200 |
| `src/hooks/useDashboard.ts` | query, refresh, stale | 70 | 180 |
| `src/components/dashboard/RangeSelector.tsx` | 24h / 7d / 30d | 55 | 150 |
| `src/components/dashboard/OverviewMetrics.tsx` | seven KPI cards | 90 | 150 |
| `src/components/dashboard/ChartFrame.tsx` | axes, legend, plot shell | 60 | 150 |
| `src/components/dashboard/TokenTrendChart.tsx` | input/output over time | 90 | 150 |
| `src/components/dashboard/LatencyChart.tsx` | p50/p95, gaps | 100 | 150 |
| `src/components/dashboard/ReliabilityChart.tsx` | stacked outcome bars | 85 | 150 |
| `src/components/dashboard/RecentGenerations.tsx` | section, cards, dialog state | 70 | 200 |
| `src/components/dashboard/RecentAttemptsTable.tsx` | desktop table headers and rows | 60 | 150 |
| `src/components/dashboard/RecentAttemptRow.tsx` | one desktop row | 60 | 120 |
| `src/components/dashboard/RecentAttemptCard.tsx` | one mobile card | 80 | 150 |
| `src/components/dashboard/StatusBadge.tsx` | completed/failed/interrupted chip | 40 | 100 |
| `src/components/dashboard/GenerationDetailsDialog.tsx` | compact metadata modal | 110 | 200 |
| `src/components/dashboard/DashboardStates.tsx` | empty, loading, error, stale | 90 | 150 |
| `src/lib/chart.ts` | geometry helpers | 90 | 150 |
| `src/lib/dashboard-format.ts` | numbers, durations, dates | 80 | 150 |

Frontend source: ~1,580 lines, including ~220 lines of shell changes. Tests:

| File | Est. |
|---|---:|
| `src/pages/DashboardPage.test.tsx` | 160 |
| `src/hooks/useDashboard.test.tsx` | 90 |
| `src/components/dashboard/RecentGenerations.test.tsx` | 100 |
| `src/components/dashboard/GenerationDetailsDialog.test.tsx` | 80 |
| `src/components/dashboard/DashboardStates.test.tsx` | 60 |
| `src/lib/chart.test.ts` | 80 |
| `src/lib/dashboard-format.test.ts` | 60 |
| `src/test/fixtures/dashboard.ts` | 80 |

Frontend tests: ~710 lines.

**Total:** ~2,680 source + ~1,870 test lines. The dashboard is roughly the size of
the existing frontend; that is why the budget is a prerequisite, not paperwork.

## 7. Milestones

### D0 — Prerequisites

- [x] Complete the code health refactor in `code-health-budget.md` §5.
- [x] Add pytest-cov, radon, Vitest coverage and ESLint limits.
- [x] Record a green baseline health report.

**Exit:** all existing tests pass, coverage floors met, no file over its fail cap.
**Done 2026-10-29.** See the D0 report in `code-health-budget.md` §4.3.

### D1 — Telemetry schema and instrumentation

- [x] Migration 0003 with columns, checks and indexes.
- [x] `ContextSelection.estimated_tokens`; `AttemptTelemetry` and `events.py` extraction.
- [x] `http_status` on provider errors; completed streams record `200`.
- [x] Finalizers persist all four fields on success, failure and interruption.
- [x] Tests: first-token timestamp, retry count, HTTP status, context estimate,
      interrupted attempt, reconciliation leaves nulls.

**Exit:** a real attempt row carries the fields; existing stream behaviour is
unchanged.
**Done 2026-10-29.** 206 backend tests pass; see the D1 report in
`code-health-budget.md` §4.3.

### D2 — Pricing and retention

- [x] Settings and `.env.example` placeholders.
- [x] Decimal estimate, availability and free-tier flag.
- [x] Startup + 24h retention task with logging.
- [x] Tests: rounding, missing rates, partial usage; old attempts deleted, recent
      attempts and all conversations/messages kept.

**Exit:** a seeded database can be aged and cleaned; cost tests do not depend on
the environment.
**Done 2026-10-29.** 216 backend tests pass; see the D2 report in
`code-health-budget.md` §4.3.

### D3 — Aggregation and API

- [x] `dashboard_queries.py`, `buckets.py`, `results.py`, `service.py`.
- [x] `routes_dashboard.py` + schemas.
- [x] Tests: empty range, exact boundaries, in-progress exclusion, terminal
      counts, percentile threshold, gap filling, recent limit, invalid range,
      no content fields.

**Exit:** `GET /api/dashboard?range=7d` matches the contract and all aggregation
tests pass.
**Done 2026-10-29.** 236 backend tests pass; see the D3 report in
`code-health-budget.md` §4.3.

### D4 — Frontend shell and data

- [x] App shell/view state, ChatPage extraction, Sidebar entry.
- [x] Dashboard API client, types, `useDashboard`, range selector.
- [x] Header, 20s refresh, manual refresh, "updated" ticker, stale banner.
- [x] Tests: navigation preserves the chat stream, default range, range refetch,
      stale with data, full error without data.

**Exit:** dashboard opens from the sidebar and the chat stream survives navigation.
**Done 2026-10-29.** 77 frontend tests pass; the KPI grid landed here and D5 is
now charts only.

### D5 — Overview and trends

- [x] Seven KPI cards, including partial usage and cost/free-tier labels (landed in D4).
- [x] `chart.ts` + `ChartFrame` + three chart components.
- [x] Tests: formatting, chart geometry, null gaps, real zero buckets, legend and
      sample counts.

**Exit:** populated and empty/sparse ranges render honestly; no chart text scales
with the SVG.
**Done 2026-10-29.** 94 frontend tests pass; token totals and averages were added
as the third section. See the D5 report in `code-health-budget.md` §4.3.

### D6 — Recent generations and details

- [x] Desktop table and mobile cards, keyboard activation.
- [x] Compact modal with status, model, tokens, TTFT, duration, HTTP, retries,
      context and sanitized error.
- [x] Tests: column mapping, 25-row limit, modal content, Escape/backdrop close,
      failed row error block.

**Exit:** every status variant is inspectable; no message content is exposed.
**Done 2026-10-29.** 106 frontend tests pass. The section splits into
`RecentAttemptsTable`, `RecentAttemptRow`, `RecentAttemptCard` and a shared
`StatusBadge`; below 1280 px the table becomes cards so nine columns never force
a horizontal scroll. The dialog shows metadata only. See the D6 report in
`code-health-budget.md` §4.3.

### D7 - States, responsive and acceptance

- [x] Loading skeleton, empty range, request failure, partial usage, missing
      pricing, insufficient samples.
- [x] Responsive pass at 1440/768/390; table → cards; modal fits.
- [x] Privacy check: response and UI never include prompts or message bodies.
- [x] Manual checklist and acceptance criteria in §9.
- [x] Milestone health report.

**Exit:** all acceptance criteria pass and the health report has no violations.
**Done 2026-10-29.** 112 frontend and 237 backend tests pass. The sidebar is an
off-canvas drawer below 1024 px, the table becomes cards below 1280 px, and the
empty state replaces zeroed sections. See the D7 report in
`code-health-budget.md` §4.3 and the manual checklist in §9.

## 8. Test plan

| Layer | Cases |
|---|---|
| Unit | range parsing, bucket generation and gap filling, percentile threshold, cost rounding, missing pricing, partial usage, chart geometry, number/date formatting |
| Integration | overview counts, active vs new conversations, user messages, status counts, success rate with in-progress attempts, token sums and partial flags, per-bucket null sums when usage is missing, TTFT/duration percentiles, recent order and limit, retention boundaries, migration constraints/indexes |
| API | payload shape, `range` validation, empty range, sanitized errors, no content leakage, error envelope |
| Frontend | default 7d, range switching, range change shows loading rather than previous range data, 20s refetch and hidden-tab pause, manual refresh, stale-with-data, error-without-data, KPI partial/cost labels, charts with null gaps, table → cards, modal keyboard/close, retry from error |
| Instrumentation | first token timestamp, automatic retry count, HTTP status from 429/5xx/mid-stream error, context estimate, interrupted attempt, crash reconciliation |
| Manual | populated dashboard, empty database, backend stopped during refresh, 24h/7d/30d, mobile sidebar, generation details for completed/failed/interrupted |

Coverage targets are in `code-health-budget.md` §3.4. Critical paths are listed
there and are required regardless of the total.

## 9. Acceptance mapping (spec 002 §11)

- [x] Dashboard opens from the sidebar.
- [x] Default range is 7 days; 24h and 30d work.
- [x] Refresh runs every 15–30s (20s) and manually.
- [x] Overview shows conversations, user messages, attempts, success rate,
      input/output tokens and estimated cost.
- [x] Trends show tokens, latency and reliability over time.
- [x] Attempts are tracked separately; manual retries are new attempts and
      automatic retries are counted inside one.
- [x] Attempt metadata is recorded when available.
- [x] Compact details are inspectable.
- [x] Missing usage or pricing is unavailable/partial, never fabricated.
- [x] Telemetry older than 30 days is cleaned up without touching conversations.
- [x] No prompts, message bodies or provider payloads are stored in telemetry.
- [x] The dashboard is useful with no data or missing provider metadata.

**Manual checklist (2026-10-29).**

| Check | Result |
|---|---|
| Populated dashboard at 1440 px | Seven KPIs in one row, two-up latency charts, 1084 px table fits without horizontal scroll |
| Tablet at 768 px | Four-up KPIs, cards instead of the table, off-canvas sidebar hidden, no horizontal overflow |
| Phone at 390 px | Two-up KPIs, full-width cards, 260 px drawer with scrim, 358×543 modal |
| Empty database | "No telemetry in this range" replaces zeroed sections; no chart or table |
| Missing pricing | Cost reads "Unavailable" with "pricing not configured"; "Unavailable" fits a 390 px card |
| Partial usage | KPI detail and token summary say "partial · usage missing" |
| Backend stopped during refresh | Covered by the stale-banner test; retry keeps the last data |
| 24h / 7d / 30d | Hourly vs daily labels switch with the range |
| Drawer | Opens from the header button, closes on Escape, backdrop and the × button |
| Details for completed/failed/interrupted | Status chips, retries, HTTP status and sanitized error block render |

## 10. Validation

```powershell
docker compose up -d db

# Backend
cd backend
uv run alembic upgrade head
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --cov=lucid --cov-branch --cov-fail-under=80
uv run radon cc src -s -a
uv run radon mi src -s

# Frontend
cd ..\frontend
npm run lint
npm run format:check
npm run typecheck
npm run test:coverage
npm run build
```

Report what ran and what did not. A green build with a red health report is not
done.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Aggregation SQL becomes one unreadable query | One query per section in `dashboard_queries.py`; no SQL in routes; test each section separately |
| Percentiles on tiny samples mislead | p95 null below 20 samples; sample count always returned |
| Instrumentation corrupts the streaming path | Telemetry is captured in memory and written in the existing terminal transaction; characterization tests before D1 |
| Chat loses its stream when opening the dashboard | Chat page stays mounted; test navigation during streaming |
| Timezones confuse daily buckets | UTC buckets and axis labels in the MVP; record the limitation |
| Retention deletes conversation history | Only `generation_attempts` rows are deleted; integration test asserts messages and conversations remain. Old messages lose attempt-derived metadata (usage, status), which is documented in §4.3. |
| Dashboard doubles the codebase | File inventory and caps above; split by chart/query; health report at each milestone |

## 12. Out of scope

Everything in spec 002 §9, plus a router, chart library, per-user timezone,
export, analytics warehouse, mutation testing and a dashboard e2e suite in the
first pass.
