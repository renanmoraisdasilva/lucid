# Chatbot MVP — Implementation Plan

**Status:** Ready for implementation, pending approval
**Version:** 1.0
**Date:** 2026-10-28
**Implements:** [`../specs/001-chatbot-mvp-specification.md`](../specs/001-chatbot-mvp-specification.md) v0.2
**Decisions:** [ADR-001](../decisions/ADR-001-gemini-provider-and-model.md) …
[ADR-006](../decisions/ADR-006-frontend-and-local-dev.md)

> This plan is the working document for implementation. The spec defines
> *what* the system must do; this plan defines *how it is built*, in what order,
> and how each milestone is proven done. If reality contradicts a decision here,
> stop, record it, and update the spec/ADR before continuing.

---

## 1. Starting state

### Repository

`chatbot_mvp` exists locally as a git repository on `main`:

| Commit | Content |
|---|---|
| `c871adf` | The specification, as the first file |
| `82c9dd9` | `.gitignore` baseline (secrets, venv, node_modules, caches) |

No remote is configured. **Creating the GitHub repository and pushing is a user
task**; CI workflows are written in Milestone 1 so they run as soon as a remote
exists.

### Environment audit (2026-10-28)

| Tool | State | Impact |
|---|---|---|
| Git | 2.47.0, identity `Renan Silva <81625697+renanmoraisdasilva@users.noreply.github.com>` | Ready |
| Docker + Compose | 29.8.2 / v5.6.0 (engine currently stopped) | Ready for the Postgres service |
| Node / npm | v22.17.1 / npm blocked by PowerShell execution policy | Frontend workable; fix `Set-ExecutionPolicy` for CurrentUser or use `npm.cmd` |
| **Python** | **Not installed** (Store alias only) | Blocks Milestone 1 |
| **uv** | **Not installed** | Blocks Milestone 1 |
| WSL | Docker Desktop distro only, no Linux distro | Confirms the host-process development layout (ADR-006) |
| gh CLI | 2.102.0, authenticated as `renanmoraisdasilva` | Available for the user to create the remote |

---

## 2. Target architecture

### 2.1 Component map

```
┌──────────────────────── browser (React + Vite, port 5173) ─────────────────────────┐
│  Sidebar (TanStack useInfiniteQuery)   Chat view   Composer   Markdown renderer    │
│                    │                       │                                       │
│                    └──── fetch /api ───────┴── SSE parser (ReadableStream) ────────┐│
└───────────────────────────────────────────────────────────────────────────────────┼┘
                                                                                     │
┌────────────────────────── FastAPI (port 8000) ─────────────────────────────────────┐│
│  API layer      routes_chat · routes_conversations · routes_health · sse · errors   ││
│  ────────────────────────────────────────────────────────────────────────────────  ││
│  Application    chat_service (orchestration) · context (budget) · attempts         ││
│                 titles · registry (attempt → asyncio.Task)                         ││
│  ────────────────────────────────────────────────────────────────────────────────  ││
│  Domain         ChatProvider protocol · provider events · domain errors            ││
│  ────────────────────────────────────────────────────────────────────────────────  ││
│  Persistence    tables (SQLAlchemy 2) · repositories · reconciliation              ││
│  Providers      gemini (google-genai) · fake                                      ││
└────────────────────────────────┬──────────────────────────────────────┬─────────────┘
                                 │                                      │
                        PostgreSQL 17 (Compose)               Gemini Interactions API
```

Dependency rule: `api → application → domain`, `application → persistence`,
`persistence → domain`, `providers → domain`. Nothing imports `providers`
except the application's factory. Nothing outside `providers/gemini.py` imports
`google.genai` (enforced by a test that walks the import graph).

### 2.2 Request lifecycle — first message of a conversation

```
1  POST /api/chat {conversation_id: null, content}
2  Validate (Pydantic): 1..16000 chars after trim; body <= 64 KiB
3  Open transaction A
4    conversation = INSERT (id=uuid7, title=derive(content), updated_at=now())
5    user_message = INSERT (seq=1)
6    attempt = INSERT (status=in_progress, attempt_no=1, provider, model)
7  Commit A                                  ← user message is durable here
8  Register attempt → asyncio.Task
9  Build request: system prompt + context.select(history) + newest user message
10 Open provider stream (store=false, system_instruction, messages)
11 Return 200 text/event-stream; emit `meta`
12 For each text delta:  append to buffer, emit `delta`
13 On interaction.completed: capture usage
14 On user Stop / disconnect: cancel task, keep buffer
15 On provider error: classify (provider_*), keep buffer
16 Open transaction B (shielded if the task was cancelled)
17   If the buffer is non-empty:
18     assistant_message = INSERT (seq = max+1, content=buffer)   ← any terminal status
19   UPDATE attempt SET status, usage, error_code, completed_at
20   UPDATE conversation SET updated_at = now()   (only if a message was inserted)
21 Commit B
22 Emit `usage` (if available) then exactly one `done` or `error`
23 Deregister attempt; close stream
```

Two edge cases that fall out of this ordering and are handled explicitly:

- **Completed but empty buffer** (model returned no text): no message row is
  inserted, `assistant_message_id` stays null, and the UI shows an
  "empty response" notice with Retry. This avoids violating
  `messages.content` non-empty.
- **Failed with empty buffer**: same shape, but the attempt records the error and
  the UI shows the error notice instead of an empty-response notice.

Key ordering rule: **commit before the terminal event.** A client that reacts to
`done` must be able to re-fetch and see the assistant message.

### 2.3 Retry lifecycle (manual)

```
1  POST /api/conversations/{cid}/messages/{mid}/retry
2  404 if conversation/message missing; 404 if message.role != user
3  409 generation_in_progress if any attempt for the conversation is in_progress
4  409 generation_already_completed if a completed attempt exists for mid
5  attempt_no = max(attempt_no for mid) + 1
6  INSERT attempt (in_progress)        ← no new user message is created
7  …identical to steps 8–23 above
```

### 2.4 Stop and disconnect

```
Stop:   POST /api/conversations/{cid}/generations/{aid}/stop
        → task = registry.get(aid)
        → task.cancel()  → provider stream closed
        → finalize as interrupted, emit `done {status: "interrupted"}`
        → 202 {attempt_id, status}  (idempotent if already terminal)

Refresh/disconnect:
        Starlette cancels the response task → the generator sees CancelledError
        → same finalization path, shielded so the DB write survives
        → no client to emit to; stream closes
```

---

## 3. Repository layout

```text
chatbot_mvp/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml              # postgres (default) + full-stack profile
├── .github/workflows/ci.yml
├── backend/
│   ├── pyproject.toml              # uv project + ruff/pyright/pytest config
│   ├── uv.lock
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── migrations/versions/
│   ├── prompts/system.md
│   ├── src/chatbot/
│   │   ├── main.py                 # app factory, lifespan (reconcile + client), routers
│   │   ├── config.py               # pydantic-settings
│   │   ├── logging.py              # structured logging, correlation ids
│   │   ├── api/
│   │   │   ├── routes_health.py
│   │   │   ├── routes_chat.py
│   │   │   ├── routes_conversations.py
│   │   │   ├── schemas.py          # request/response Pydantic models
│   │   │   ├── errors.py           # exception → JSON error mapping
│   │   │   └── sse.py              # frame encoder, terminal-discipline helper
│   │   ├── application/
│   │   │   ├── chat_service.py
│   │   │   ├── context.py
│   │   │   ├── attempts.py
│   │   │   ├── titles.py
│   │   │   └── registry.py
│   │   ├── domain/
│   │   │   ├── enums.py            # Role, AttemptStatus, ErrorCode
│   │   │   ├── errors.py           # provider/domain exception hierarchy
│   │   │   └── provider.py         # ChatProvider protocol + events
│   │   ├── persistence/
│   │   │   ├── db.py
│   │   │   ├── tables.py
│   │   │   ├── repositories.py
│   │   │   └── reconciliation.py
│   │   └── providers/
│   │       ├── gemini.py
│   │       └── fake.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── api/
│       └── fixtures/               # recorded provider event frames
└── frontend/
    ├── package.json
    ├── vite.config.ts              # /api proxy → 127.0.0.1:8000, Tailwind plugin, Vitest config
    ├── Dockerfile
    ├── index.html
    └── src/
        ├── main.tsx / App.tsx
        ├── api/{client.ts,chatStream.ts,types.ts}
        ├── hooks/{useConversations.ts,useConversation.ts,useChatStream.ts}
        ├── components/…
        └── pages/ChatPage.tsx
```

---

## 4. Data model (DDL)

PostgreSQL 17, `timestamptz` everywhere, UUIDv7 generated in Python.

```sql
CREATE TABLE conversations (
    id          uuid        PRIMARY KEY,
    title       text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT conversations_title_len CHECK (char_length(title) BETWEEN 1 AND 80)
);
CREATE INDEX ix_conversations_order ON conversations (updated_at, id);
-- A backward index scan serves "ORDER BY updated_at DESC, id DESC".

CREATE TABLE messages (
    id              uuid        PRIMARY KEY,
    conversation_id uuid        NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            text        NOT NULL CHECK (role IN ('user','assistant')),
    content         text        NOT NULL CHECK (char_length(content) > 0),
    seq             integer     NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_messages_seq UNIQUE (conversation_id, seq)
);
CREATE INDEX ix_messages_conversation_seq ON messages (conversation_id, seq);

CREATE TABLE generation_attempts (
    id                   uuid        PRIMARY KEY,
    conversation_id      uuid        NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_message_id      uuid        NOT NULL REFERENCES messages(id)      ON DELETE CASCADE,
    assistant_message_id uuid        REFERENCES messages(id)               ON DELETE SET NULL,
    attempt_no           integer     NOT NULL CHECK (attempt_no >= 1),
    status               text        NOT NULL
                                     CHECK (status IN ('in_progress','completed','failed','interrupted')),
    provider             text        NOT NULL,
    model                text        NOT NULL,
    error_code           text,
    error_message        text,
    input_tokens         integer,
    output_tokens        integer,
    thought_tokens       integer,
    total_tokens         integer,
    usage_raw            jsonb,
    started_at           timestamptz NOT NULL DEFAULT now(),
    completed_at         timestamptz,
    CONSTRAINT uq_attempt_no UNIQUE (user_message_id, attempt_no)
);
CREATE INDEX ix_attempts_conversation ON generation_attempts (conversation_id);
CREATE INDEX ix_attempts_user_message ON generation_attempts (user_message_id);
CREATE UNIQUE INDEX uq_attempts_one_active_per_conversation
    ON generation_attempts (conversation_id) WHERE status = 'in_progress';
```

### Invariants and why

| Invariant | Mechanism | Failure it prevents |
|---|---|---|
| One active generation per conversation | Partial unique index | Two concurrent streams writing to one transcript |
| No duplicate message positions | `UNIQUE (conversation_id, seq)` | Out-of-order or duplicated rendering |
| Attempt numbering dense per user message | `UNIQUE (user_message_id, attempt_no)` | Retry bookkeeping ambiguity |
| Conversation delete is total | `ON DELETE CASCADE` | Orphaned messages/attempts |
| Assistant message survives its attempt's deletion | `ON DELETE SET NULL` | Accidentally deleting content with metadata |
| Title bounded at the source | `CHECK` + app-side rule | Unbounded titles in the sidebar query |

### Title derivation (`application/titles.py`)

```
normalize: Unicode NFKC → collapse whitespace runs → trim → strip control chars
if empty                     → "New chat"
if len(code_points) <= 80    → normalized
else:
    window = first 80 code points
    cut = last index of " " within the final 20 code points of window
    title = window[:cut] if cut > 0 else window
    title = title.rstrip(" ,.;:-")
    if title is empty        → window          # never emit an empty title
```
Unit tests cover: empty/whitespace, exactly 80, 81 with a space at 79, 81 with no
space (hard cut), emoji (code points, not bytes), very long single word, and
titles that would end in punctuation after a cut.

---

## 5. API contract

Base path `/api`. JSON everywhere except the SSE streams.

### 5.1 Endpoints

| Method | Path | Purpose | Success |
|---|---|---|---|
| GET | `/api/health` | Liveness, no dependencies | 200 `{"status":"ok"}` |
| GET | `/api/health/ready` | DB reachability | 200 or 503 |
| POST | `/api/chat` | Send message, stream reply | 200 `text/event-stream` |
| GET | `/api/conversations` | Cursor list | 200 |
| GET | `/api/conversations/{id}` | Conversation + messages | 200 |
| DELETE | `/api/conversations/{id}` | Permanent delete | 204 |
| POST | `/api/conversations/{cid}/messages/{mid}/retry` | Retry message | 200 `text/event-stream` |
| POST | `/api/conversations/{cid}/generations/{aid}/stop` | Stop generation | 202 |

### 5.2 `POST /api/chat`

```json
{ "conversation_id": "0192f3c1-…" , "content": "Explain SSE vs WebSockets" }
```
`conversation_id` is `null` (or omitted) for a new conversation. Response:
`text/event-stream`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`,
`Content-Type: text/event-stream; charset=utf-8`.

### 5.3 `GET /api/conversations?cursor=&limit=20`

```json
{
  "items": [
    { "id": "0192f3c1-…", "title": "Explain SSE vs WebSockets",
      "created_at": "2026-10-28T18:02:11.231Z",
      "updated_at": "2026-10-28T18:04:02.918Z",
      "active_attempt_id": null }
  ],
  "next_cursor": "MjAyNi0xMC0yOFQxODowNDowMi45MThafDAxOTJmM2Mx…",
  "has_more": true
}
```

### 5.4 `GET /api/conversations/{id}`

```json
{
  "id": "0192f3c1-…",
  "title": "Explain SSE vs WebSockets",
  "created_at": "…", "updated_at": "…",
  "active_attempt_id": null,
  "messages": [
    { "id": "…", "role": "user", "seq": 1, "content": "Explain SSE vs WebSockets",
      "created_at": "…",
      "attempt": { "id": "…", "status": "completed", "model": "gemini-3.5-flash-lite",
                   "retryable": false, "error_code": null,
                   "usage": { "input_tokens": 812, "output_tokens": 240,
                              "thought_tokens": 0, "total_tokens": 1052 } } },
    { "id": "…", "role": "assistant", "seq": 2, "content": "Server-Sent Events…",
      "created_at": "…",
      "attempt": { "id": "…", "status": "completed", … } }
  ]
}
```

Message semantics:

- On an **assistant** message, `attempt` is the attempt that produced it.
- On a **user** message, `attempt` is the most recent attempt targeting it. This
  is what lets the UI show "failed — Retry" with no assistant message present.
- `usage` is `null` when the provider returned no metadata; the UI renders
  "usage unavailable" rather than a fabricated number.
- `retryable` is computed server-side from the retry rules (ADR-005) so the
  frontend never re-implements the matrix.

### 5.5 Error envelope (HTTP-level)

```json
{ "error": { "code": "generation_in_progress",
             "message": "A response is already being generated for this conversation.",
             "details": { "attempt_id": "0192f3c1-…" } } }
```

### 5.6 Error taxonomy

| Code | HTTP | Retryable | Notes |
|---|---|---|---|
| `validation_error` | 422 | no | Pydantic detail flattened to `details.fields` |
| `payload_too_large` | 413 | no | Body > 64 KiB |
| `invalid_cursor` | 400 | no | Undecodable/foreign cursor |
| `conversation_not_found` | 404 | no | |
| `message_not_found` | 404 | no | |
| `attempt_not_found` | 404 | no | |
| `generation_in_progress` | 409 | no | `details.attempt_id` |
| `generation_already_completed` | 409 | no | Retry after success |
| `context_too_large` | 422 | no | Even the newest message plus system prompt exceeds budget |
| `provider_rate_limited` | stream | yes | 429 / quota |
| `provider_timeout` | stream | yes | Request or idle timeout |
| `provider_unavailable` | stream | yes | 5xx, connection reset, `gateway_timeout` |
| `provider_invalid_request` | stream | no | 400-class provider rejection |
| `provider_safety_blocked` | stream | no | Refusal/safety stop |
| `provider_stream_error` | stream | no | Malformed/aborted stream |
| `internal_error` | 500 / stream | no | Logged with correlation id, never leaks detail |

`process_restart` is an **attempt-level** code written by reconciliation; it is
never returned as an API error. It maps to `interrupted` + retryable in the UI.

---

## 6. SSE event contract

Exactly one terminal event per stream. Frames are `event:` + `data:` lines with
`\n\n` separators. A comment heartbeat (`: ping`) is emitted every 15s of
silence to keep intermediaries from idling the connection.

### 6.1 `meta` (always first)

```
event: meta
data: {"conversation_id":"0192f3c1-…","conversation_title":"Explain SSE vs WebSockets",
       "user_message_id":"0192f3c2-…","attempt_id":"0192f3c3-…",
       "model":"gemini-3.5-flash-lite","is_new_conversation":true}
```
The client uses this to switch from `new` to `/c/{id}` without a second request.

### 6.2 `delta`

```
event: delta
data: {"text":"Server-Sent "}
```

### 6.3 `usage` (optional, before terminal)

```
event: usage
data: {"input_tokens":812,"output_tokens":240,"thought_tokens":0,"total_tokens":1052}
```
Any field may be `null`. Emitted only when the provider reported usage, and only
after the terminal transaction commits.

### 6.4 `done` (terminal)

```
event: done
data: {"attempt_id":"0192f3c3-…","status":"completed",
       "assistant_message_id":"0192f3c4-…","finish_reason":"stop"}
```
`status` is `completed` or `interrupted`. `finish_reason` is `stop`,
`length`, or `interrupted`; it is diagnostic only.

### 6.5 `error` (terminal)

```
event: error
data: {"code":"provider_rate_limited",
       "message":"The model is rate limited right now. Try again in a moment.",
       "retryable":true,"attempt_id":"0192f3c3-…"}
```
The human-readable `message` is from a fixed mapping; provider text is never
forwarded.

### 6.6 Client rules

- Buffer `delta` text into the open assistant bubble.
- On `done`: keep the text, attach usage, re-enable the composer, refresh the
  conversation and the sidebar list.
- On `error`: keep any streamed text, show the notice with Retry when
  `retryable`, re-enable the composer.
- On stream close **without** a terminal event: treat as interrupted, show the
  partial text, offer Retry.
- Abort the `fetch` with an `AbortController` on Stop and on unmount.

---

## 7. Configuration

`.env` (backend), with `.env.example` committed containing placeholders only.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://chatbot:chatbot@localhost:5432/chatbot` | DB connection |
| `GEMINI_API_KEY` | — (required) | Provider credential, backend only |
| `PROVIDER` | `gemini` | `gemini` or `fake`; tests force `fake` |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model id — the only place a model is named |
| `GEMINI_TIMEOUT_SECONDS` | `60` | Overall request timeout |
| `GEMINI_MAX_OUTPUT_TOKENS` | `2048` | Cap on generated tokens |
| `GENERATION_MAX_RETRIES` | `2` | Automatic retries per attempt |
| `RETRY_BASE_DELAY_MS` | `1000` | Exponential base |
| `RETRY_MAX_DELAY_MS` | `8000` | Backoff cap |
| `RETRY_JITTER` | `true` | Disabled in tests for determinism |
| `CONTEXT_MAX_INPUT_TOKENS` | `20000` | History + system prompt budget |
| `CONTEXT_RESERVED_OUTPUT_TOKENS` | `4096` | Reserved for the response |
| `CONTEXT_SAFETY_MARGIN_TOKENS` | `512` | Estimation error allowance |
| `CONTEXT_MAX_MESSAGES` | `60` | Hard cap regardless of budget |
| `MAX_USER_MESSAGE_CHARS` | `16000` | Validated per message |
| `MAX_REQUEST_BODY_BYTES` | `65536` | Middleware cap |
| `SYSTEM_PROMPT_PATH` | `prompts/system.md` | Version-controlled prompt |
| `LOG_LEVEL` | `INFO` | Never logs prompt/response content |
| `RECONCILE_ON_STARTUP` | `true` | Stranded attempt cleanup |

Validation rules at startup: `GEMINI_API_KEY` present when `PROVIDER=gemini`;
prompt file exists, is non-empty, and under 20k characters; reserved output is
less than the input budget. Fail fast with a clear message, never a stack trace.

---

## 8. Context construction (`application/context.py`)

```
budget_msgs = CONTEXT_MAX_INPUT_TOKENS - RESERVED_OUTPUT - MARGIN - tokens(system_prompt)
if budget_msgs <= 0: raise ContextTooLarge

selected = []
used = 0
for message in reversed(history):            # newest first
    cost = estimate_tokens(message.content)  # ceil(code_points/4) + 4 overhead
    if used + cost > budget_msgs or len(selected) >= CONTEXT_MAX_MESSAGES:
        break
    selected.append(message); used += cost

selected.reverse()
while selected and selected[0].role == "assistant":
    selected.pop(0)                          # history must start with a user turn

if not selected or selected[-1].role != "user":
    raise ContextTooLarge                    # newest user message must always fit
```

Rules:

- `history` is the persisted transcript **excluding** the message being answered
  when the caller passes it separately.
- Estimates are marked as estimates in logs (`context_estimated_tokens`); actual
  usage comes from the provider and is what gets stored/displayed.
- A provider-side `context_too_large` (or a 400 mentioning input length) is
  translated to the same non-retryable code.
- Milestone 5 includes a spike: if the Interactions API exposes a token-count
  endpoint, use it for a single pre-flight count when the estimate is within 10%
  of the budget; otherwise keep the heuristic. Record the outcome in
  `docs/architecture/gemini-adapter-notes.md`.

---

## 9. Milestones

Each milestone is a reviewable slice: code + tests + a demonstrable outcome.
Do not start the next milestone with failing checks or unchecked exit criteria.

### Milestone 0 — Design close (this document)

| # | Task | Status |
|---|---|---|
| 0.1 | Resolve every open decision from spec v0.1 | ✅ done (spec §15) |
| 0.2 | Record consequential decisions as ADRs | ✅ done (ADR-001…006) |
| 0.3 | Define data model, API contract, SSE contract | ✅ done (sections 4–6) |
| 0.4 | Define milestones, tests, and risks | ✅ done (this document) |
| 0.5 | User review and approval of spec v0.2 + plan | ⬜ pending |
| 0.6 | Architecture diagram checked into `docs/architecture/` | ⬜ M1 |

**Exit:** no open question blocks Milestone 1; approval recorded.

---

### Milestone 1 — Foundation

Goal: a running skeleton with quality gates, no product features.

| # | Task |
|---|---|
| 1.1 | Install `uv` and Python 3.12 on Windows; document the exact commands in `README.md` |
| 1.2 | `backend/pyproject.toml`: fastapi, uvicorn, pydantic-settings, sqlalchemy[asyncio], asyncpg, alembic, google-genai, httpx, uuid-utils; dev group: ruff, pyright, pytest, pytest-asyncio, httpx (test client), coverage |
| 1.3 | `main.py` app factory, `config.py` settings, structured logging with request/attempt correlation ids |
| 1.4 | `GET /api/health` and `GET /api/health/ready` (DB check, 503 when unreachable) |
| 1.5 | Ruff + Pyright (strict) + pytest config in `pyproject.toml` |
| 1.6 | `docker-compose.yml`: postgres:17 with healthcheck, named volume, port 5432 |
| 1.7 | Alembic init, empty baseline revision, documented `uv run alembic upgrade head` |
| 1.8 | Frontend scaffold: Vite React TS (strict), Tailwind, ESLint, Prettier, Vitest; shell page that calls `/api/health` |
| 1.9 | Vite dev proxy `/api` → `http://127.0.0.1:8000` |
| 1.10 | `.github/workflows/ci.yml`: backend job (ruff, pyright, pytest with postgres service) + frontend job (eslint, tsc, vitest) |
| 1.11 | `README.md`: prerequisites, quickstart, project layout, dependency justification table |
| 1.12 | `.env.example` with placeholders |

**Tests:** health returns 200; readiness returns 503 with the DB stopped and 200
when up; `alembic upgrade head` succeeds on a clean database; a single frontend
smoke test renders the shell.

**Demo:** `docker compose up -d db`, `uv run uvicorn chatbot.main:app --reload`,
`npm run dev`, health indicator green in the browser.

**Exit:** CI green on the first push (once the remote exists), all four quality
commands pass locally, no feature code committed.

---

### Milestone 2 — Persistence and conversation management

| # | Task |
|---|---|
| 2.1 | `tables.py` with the three models, constraints, and indexes from section 4 |
| 2.2 | Alembic revision `0002_chat_schema` (baseline `0001_baseline` was created in Milestone 1); downgrade verified |
| 2.3 | `repositories.py`: conversation create/get/touch/delete, message insert with `seq` allocation under a row lock, attempt create/update/fetch, keyset list |
| 2.4 | `titles.py` + unit tests (section 4 cases) |
| 2.5 | Cursor encode/decode + unit tests (round-trip, malformed, foreign) |
| 2.6 | `GET /api/conversations`, `GET /api/conversations/{id}`, `DELETE /api/conversations/{id}` |
| 2.7 | Response schemas incl. `attempt` summaries and `active_attempt_id` |
| 2.8 | Integration tests (section 10.2) |

**Demo:** seed two conversations via a test helper; page through them; delete one
and observe cascade.

**Exit:** pagination is stable across concurrent inserts (test proves no
duplicates or gaps); cascade delete verified; no provider code exists yet.

---

### Milestone 3 — Provider boundary and Gemini adapter

| # | Task |
|---|---|
| 3.1 | `domain/provider.py`: protocol, request/event dataclasses |
| 3.2 | `domain/errors.py`: error hierarchy with `code` + `retryable` |
| 3.3 | `providers/fake.py`: scripted deltas, configurable usage, injectable failures, injectable delays |
| 3.4 | **Spike:** confirm on the current SDK — async client namespace for `interactions.create`, `stream=True`, `store=False`, `system_instruction` placement, input shape for multi-turn history, usage field names, mid-stream error payload. Write findings to `docs/architecture/gemini-adapter-notes.md` |
| 3.5 | `providers/gemini.py`: request mapping, event mapping (`step.delta`/text → `TextDelta`, `interaction.completed` → `StreamCompleted`, `thought*`/tool steps ignored), timeout, error translation |
| 3.6 | Import-graph test: `google.genai` appears only in `providers/gemini.py` |
| 3.7 | `prompts/system.md` + loader with startup validation |
| 3.8 | Provider factory from settings (`PROVIDER=fake` for tests) |
| 3.9 | `POST /api/chat` as **temporary JSON** endpoint (drains the stream to a string) to validate orchestration end to end |
| 3.10 | Adapter tests over recorded fixture frames; error-translation table test |

**Demo:** with `PROVIDER=fake`, `POST /api/chat` returns a persisted assistant
message. With a real key, one manual call to `gemini-3.5-flash-lite` succeeds and
is documented (not automated).

**Exit:** no SDK type crosses the provider boundary; fake provider makes the
whole request path testable; live call verified once and noted with date/model.

---

### Milestone 4 — Streaming chat

| # | Task |
|---|---|
| 4.1 | `api/sse.py`: frame encoder, heartbeat, terminal-event discipline (a stream cannot end without exactly one terminal event) |
| 4.2 | `application/registry.py`: attempt→task map with async lock, register/deregister/cancel, lookup |
| 4.3 | `application/chat_service.py`: full orchestration from section 2.2, commit-before-terminal, shielded finalization |
| 4.4 | `POST /api/chat` becomes SSE; `meta` first (replaces the temporary JSON shape) |
| 4.5 | `POST …/stop` endpoint, idempotent |
| 4.6 | Disconnect handling via `CancelledError`; shield the DB write |
| 4.7 | Retry endpoint returning SSE, reusing the user message |
| 4.8 | Frontend: `chatStream.ts` parser (handles `\r\n` and `\n`, multi-line `data:`, ignores comments), `useChatStream`, minimal chat UI, Stop button, composer lock |
| 4.9 | API tests (section 10.3) |

**Demo:** stream a response token by token; press Stop and see "interrupted" with
the partial text; refresh mid-generation and find the partial text after reload;
kill the network to force a failure and Retry without duplicating the message.

**Exit:** exactly one terminal event in every path including disconnect; no
duplicate user messages under retry; composer is locked while streaming.

---

### Milestone 5 — Context, usage, and resilience

| # | Task |
|---|---|
| 5.1 | `context.py` selection + unit tests at budget boundaries |
| 5.2 | Token-count spike (see section 8) and documented decision |
| 5.3 | `usage` event, persistence of usage fields + `usage_raw`, `usage` in the conversation payload, `UsageBadge` with an "unavailable" state |
| 5.4 | Retry policy module: eligibility matrix, backoff computation with injectable clock/jitter |
| 5.5 | Retry loop in `chat_service`: pre-first-token only, same attempt, counted in logs |
| 5.6 | `reconciliation.py` at startup + test with a planted `in_progress` row |
| 5.7 | `context_too_large` mapping and user-facing message |
| 5.8 | Tests (section 10.1 retry/context rows, 10.4) |

**Demo:** force a 429 with the fake provider and watch the retries succeed
invisibly; force a permanent failure and see the error plus Retry; restart the
backend mid-generation and observe the reconciled interrupted attempt.

**Exit:** retry matrix fully tested; usage shown when present and "unavailable"
when absent; no attempt can stay `in_progress` after restart.

---

### Milestone 6 — UI polish and acceptance

| # | Task |
|---|---|
| 6.1 | Sidebar: `useInfiniteQuery`, New chat, ordering, active conversation highlight, delete with confirmation |
| 6.2 | Markdown pipeline: `react-markdown` + `remark-gfm` + `rehype-sanitize` + `rehype-highlight`; `CodeBlock` with copy button and language label |
| 6.3 | Sanitization tests: `<script>`, `javascript:` links, `onerror` attributes, raw HTML, `<iframe>` all neutralized |
| 6.4 | Interrupted/failed markers, Retry affordance, error notices, usage badge placement |
| 6.5 | Composer: disabled while generating, Enter to send / Shift+Enter newline, char counter near the 16k limit, autoscroll that respects manual scroll-up |
| 6.6 | Title ellipsis, empty states, loading skeletons, error boundary |
| 6.7 | Full-stack Compose profile (backend + frontend Dockerfiles, healthchecks, `depends_on`) |
| 6.8 | README final pass: setup, architecture summary, trade-offs, known limitations, manual acceptance results |
| 6.9 | Accessibility pass: labels, focus order, keyboard-only operation, contrast |
| 6.10 | Run the spec §12 acceptance checklist and record results |

**Demo:** clean clone → documented steps → working chat with Markdown, code
blocks, stop, retry, delete, pagination, restart durability.

**Exit:** every acceptance criterion in spec §12 is checked with evidence.

---

## 10. Test plan

### 10.1 Unit (pytest)

| Area | Cases |
|---|---|
| Title derivation | empty, whitespace, exactly 80, 81 with/without space, emoji, punctuation tail |
| Cursor | round-trip, malformed, stale, tiebreaker correctness |
| Context selection | fits, boundary exactly at budget, over budget, hard message cap, leading assistant dropped, newest message alone too large → `ContextTooLarge` |
| Retry eligibility | each error code → retryable/not, retry-after-first-token rejected, max-retries exhausted |
| Backoff | monotonic growth, cap respected, jitter deterministic when disabled |
| Status transitions | legal/illegal attempt transitions rejected |
| Usage mapping | full, partial, missing → `None`, raw preserved |
| Error translation | provider exception → domain error, no SDK type leaks |

### 10.2 Integration (pytest + real PostgreSQL)

| Case |
|---|
| Conversation created only on first message; "New chat" alone writes nothing |
| Message `seq` is dense and ordered under concurrent inserts |
| Cascade delete removes messages and attempts |
| `updated_at` bumps on message insert, not on attempt-only status change |
| Pagination stable while new conversations are inserted between pages |
| Partial unique index rejects a second `in_progress` attempt |
| Alembic upgrade from empty and downgrade/upgrade cycle |

### 10.3 API/stream (pytest + ASGI client, fake provider)

| Case |
|---|
| `meta` arrives first and carries ids |
| Deltas arrive incrementally (multiple frames, not one blob) |
| Exactly one terminal event on success, failure, stop, and disconnect |
| Provider failure pre-first-token: attempt `failed`, user message retained, `error` retryable |
| Provider failure post-first-token: partial message visible, attempt `failed`, retry offered |
| Stop: attempt `interrupted`, partial text persisted, idempotent second Stop |
| Disconnect: same as stop, with no client to notify |
| Second message during generation: `409` + `attempt_id` |
| Retry reuses the user message, increments `attempt_no`, creates one assistant message |
| Retry after success: `409 generation_already_completed` |
| Oversized message: `422`; oversized body: `413` |
| Unknown ids: `404` with the right code |
| Malformed cursor: `400 invalid_cursor` |
| Startup reconciliation: planted `in_progress` → `interrupted`/`process_restart` |

### 10.4 Frontend (Vitest + RTL)

| Case |
|---|
| SSE parser: multi-frame chunk, split frame across chunks, CRLF, comments, terminal detection |
| Streaming render appends text to the open bubble |
| Composer disabled while streaming; re-enabled after terminal |
| Stop calls the endpoint and keeps partial text |
| Retry sends the original message id |
| Markdown sanitization blocks scripts and `javascript:` links |
| Code block copy writes to clipboard |
| Sidebar pagination loads the next page on scroll |
| Usage badge shows values or "unavailable" |

### 10.5 Manual / E2E checklist

Spec §12, executed at Milestone 6 and recorded in the README:

- clean clone + documented steps → running app
- streamed response end to end
- refresh during generation → interrupted partial
- failed generation → retry without duplicate message
- conversations survive `docker compose restart` and backend restart
- delete removes from sidebar and database
- markdown, code highlighting, copy button behave

---

## 11. Validation commands

Run before every commit that changes a language; run all before closing a
milestone. PowerShell, from the repo root.

```powershell
# Database
docker compose up -d db
docker compose ps

# Backend
cd backend
uv sync
uv run alembic upgrade head
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q

# Frontend
cd ..\frontend
npm run lint
npm run format:check
npm run typecheck
npm test

# Full-stack acceptance path
cd ..
docker compose --profile full up --build
```

Report exactly what ran and what did not. Never claim a check passed without
running it.

---

## 12. Risks and mitigations

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| R1 | **Model churn.** `gemini-3.5-flash-lite` may be deprecated, renamed, or removed from the free tier. Google narrowed free-tier model access materially during 2026 and per-model limits are no longer published in a table. | High over time | Model id exists only in config; every attempt records provider+model; adapter contract tests pin the event/usage shape; startup logs the configured model. **Post-MVP: model registry + picker.** |
| R2 | **Interactions API churn** (it already shipped a breaking-change round in May 2026). | Medium | Pin `google-genai` to a minor range, isolate in one module, cover with fixture-based tests, document the migration path to `generateContent` as a fallback. |
| R3 | **No server-side cancel** → quota used after Stop. | Certain, low impact | Accepted in ADR-001; `GEMINI_MAX_OUTPUT_TOKENS` caps waste; free tier makes cost zero. |
| R4 | **Buffered partial text lost on crash.** | Low | Accepted; startup reconciliation to `interrupted`/`process_restart`; the user can retry. |
| R5 | **In-process registry breaks with >1 worker.** | Low in MVP | Single-process uvicorn; document it; DB index still enforces the data invariant. Revisit with an ADR if scaling. |
| R6 | **Free-tier rate limits unknown per model.** | Medium | 429 classification + 2 jittered retries; tests use the fake provider; manual smoke runs kept small; check AI Studio for current limits before demos. |
| R7 | **Windows dev friction** (no WSL distro, npm execution policy, Docker engine stopped). | Medium | Host-run processes; `npm.cmd` or fixed execution policy; document `docker compose` start step. |
| R8 | **Python/uv absent.** | Certain | First task of Milestone 1. |
| R9 | **SSE buffering through proxies/dev server.** | Low locally, likely in deployment | `X-Accel-Buffering: no`, no-cache headers, Vite proxy config, heartbeat comments. |
| R10 | **Context estimate vs provider tokenization divergence.** | Medium | Estimates used only for selection; provider usage stored and displayed; conservative margin; spike in M5. |
| R11 | **Scope creep** (search, regeneration, auth, tools). | Medium | Explicit non-goals in spec §3; deferred list in spec §15; any addition requires an interview and a spec update. |

---

## 13. Post-MVP backlog (explicitly not now)

Ordered by expected value for the roadmap, not committed:

1. **Model registry + model picker** — directly addresses R1: a config-driven
   list of models with capability metadata, a dropdown in the UI, and per-attempt
   model attribution. Likely the natural next increment after the MVP.
2. Conversation summarization for long histories (replaces truncation).
3. Regenerate response and edit-and-resend.
4. Conversation search and export.
5. Authentication + multi-user isolation (needed before any deployment).
6. Deployment (container images, managed Postgres, secrets) and Terraform.
7. Second provider adapter as a portability exercise.
8. Small evaluation harness for answer quality (prepares the RAG project).
9. Usage and cost dashboard.
10. Rate limiting and request quotas for a public deployment.

---

## 14. Definition of done (per task)

Adapted from roadmap §8. A task is done when the applicable boxes hold:

- [ ] Behaviour matches an approved spec clause or this plan
- [ ] Inputs validated at the boundary; outputs typed
- [ ] Failure paths handled (timeout, provider error, disconnect, invalid input)
- [ ] Security implications considered (no secrets, no content logging, no raw HTML)
- [ ] Automated tests cover the behaviour, including at least one failure case
- [ ] `ruff check`, `ruff format --check`, `pyright`, `pytest` pass (backend)
- [ ] `npm run lint`, `npm run typecheck`, `npm test` pass (frontend)
- [ ] No new dependency without a stated reason in the README table
- [ ] Docs/ADR/spec updated if a decision changed
- [ ] The change can be explained in an interview: what, why, alternatives, failure modes

---

## 15. Working agreement for implementation

- One task at a time from this plan; report the task id in the change summary.
- Small diffs; no opportunistic refactors in feature commits.
- If a task reveals a contradiction with the spec or an ADR: stop, summarise the
  conflict, propose options, and wait for a decision before coding around it.
- Every milestone ends with the validation commands in section 11 actually run,
  plus a one-paragraph note of what is demonstrable and what remains.
