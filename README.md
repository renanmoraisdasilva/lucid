# Lucid

A single-user, ChatGPT-style chatbot built as a learning project: FastAPI +
PostgreSQL backend, React + TypeScript frontend, streamed responses from Gemini.

The point is not the chatbot. It is to build, test, and explain the complete
lifecycle of an LLM-backed application — request, context construction, provider
streaming, persistence, cancellation, failure handling, and observability —
without hiding behind a framework or an agent library.

## Status

**Milestone 4 (streaming chat) complete.** Replies stream over SSE with `meta`,
`delta`, `usage`, and exactly one terminal `done`/`error` event. Stop, client
disconnect, retry, and the 409 concurrency rule are implemented and tested. The
temporary JSON endpoint is gone. Verified against live Gemini: incremental
deltas, `usage` (`117 in / 1 out`), and a deliberate mid-stream abort that
persisted a 43-character interrupted message with no active attempt left behind.

The React app is functional: conversation list, streaming thread, Stop, Retry,
errors, usage. Visual polish against `docs/screen-mockups/` is Milestone 6.

| Milestone | State |
|---|---|
| 0 — Design close | ✅ |
| 1 — Foundation | ✅ |
| 2 — Persistence and conversations | ✅ |
| 3 — Provider boundary and Gemini adapter | ✅ |
| 4 — Streaming chat | ✅ |
| 5 — Context, usage, resilience | ⬜ next |
| 6 — UI polish and acceptance | ⬜ |

## Documentation

| Document | Purpose |
|---|---|
| [`docs/specs/001-lucid-specification.md`](docs/specs/001-lucid-specification.md) | What the system must do: scope, non-goals, UX, data model, acceptance criteria |
| [`docs/plans/implementation-plan.md`](docs/plans/implementation-plan.md) | How it gets built: architecture, DDL, API and SSE contracts, milestones, tests, risks |
| [`docs/decisions/`](docs/decisions/) | ADRs for the consequential choices (provider, data model, streaming, ids, failures, frontend) |
| [`docs/architecture/`](docs/architecture/) | Adapter notes: verified SDK behaviour, event shapes, error mapping |
| [`docs/screen-mockups/`](docs/screen-mockups/) | Static HTML previews of every UI state, plus the shared design tokens and shell |

Read the specification first, then the plan. The ADRs explain the decisions that
the spec leaves as outcomes rather than reasoning.

## Scope in one paragraph

One user, no authentication. Send a message, watch the reply stream in, stop it
mid-flight, retry a failure, browse and delete conversations, read Markdown with
syntax-highlighted code blocks. Everything persists in PostgreSQL. Full
conversations are stored; only a bounded, budgeted slice is sent to the model.
No RAG, no agents, no tools, no file uploads, no cloud deployment.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Persistence | PostgreSQL 17, SQLAlchemy 2.x async, asyncpg, Alembic |
| Model | Gemini `gemini-3.5-flash-lite` via the Interactions API (`google-genai`) — Milestone 3 |
| Streaming | Server-Sent Events over `POST`, parsed with `fetch` — Milestone 4 |
| Frontend | React 19 + TypeScript, Vite, Tailwind CSS |
| Quality | Ruff, Pyright (strict), pytest, ESLint, Prettier, Vitest, GitHub Actions |
| Local dev | PostgreSQL in Docker Compose; API and web on the host |

### Why these dependencies

| Dependency | Reason |
|---|---|
| `uv` | Reproducible Python toolchain and lockfile; also provisions the interpreter |
| `fastapi`, `uvicorn` | Typed async HTTP framework with streaming support |
| `pydantic`, `pydantic-settings` | Boundary validation and typed configuration |
| `sqlalchemy[asyncio]`, `asyncpg` | Async persistence with explicit transactions |
| `alembic` | Versioned schema migrations |
| `ruff`, `pyright`, `pytest` | Lint/format, static typing, tests |
| `react`, `react-dom`, `vite` | UI runtime and dev server |
| `tailwindcss` | Styling without a bespoke CSS system |
| `eslint`, `prettier`, `vitest`, `@testing-library/*` | Frontend quality gates |
| `google-genai` | Gemini Interactions API client (added in Milestone 3) |

## Prerequisites

- Docker Desktop with Compose v2+
- [`uv`](https://docs.astral.sh/uv/) and Python 3.12 (uv can install the
  interpreter itself)
- Node.js 22+
- A Gemini API key, free tier is sufficient (Milestone 3 onwards)

### Installing the toolchain on Windows

Verified on this machine on 2026-10-28:

```powershell
# uv, which also manages the Python interpreter
winget install --id=astral-sh.uv -e

# Managed CPython 3.12 (no python.org installer needed)
uv python install 3.12

# npm ships .ps1 wrappers that a Restricted policy blocks
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

A new shell is required after `winget install` for `uv` to be on `PATH`.

## Quickstart

```powershell
# 1. Configuration
Copy-Item .env.example .env      # edit if you want different credentials

# 2. PostgreSQL
docker compose up -d db

# 3. Backend (terminal 1)
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn lucid.main:app --reload

# 4. Frontend (terminal 2)
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. The page reports `API: ok` when the dev proxy can
reach the backend.

Configuration is read from the repository-root `.env` first, then `backend/.env`,
so a local override next to the code wins. `PROVIDER=gemini` requires
`GEMINI_API_KEY`; `PROVIDER=fake` runs the scripted provider with no key and no
network access.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness, no dependency checks |
| `GET /api/health/ready` | Readiness, includes a database round trip |
| `GET /api/conversations` | Cursor-paginated list, most recently updated first |
| `GET /api/conversations/{id}` | Conversation with messages and attempt metadata |
| `DELETE /api/conversations/{id}` | Permanent delete, messages and attempts cascade |
| `POST /api/chat` | Send a message; returns `text/event-stream` |
| `POST /api/conversations/{cid}/messages/{mid}/retry` | Retry a user message; streams a new attempt |
| `POST /api/conversations/{cid}/generations/{aid}/stop` | Cooperative stop, `202`, idempotent |
| `/docs` | OpenAPI UI (development convenience) |

Errors use one envelope: `{"error": {"code", "message", "details"}}`.

## Development commands

```powershell
# Backend, from backend/
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
uv run alembic upgrade head

# Frontend, from frontend/
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
```

Integration tests run against the Compose database and **truncate the chat
tables** between cases. They skip automatically when no database is reachable.
Point them elsewhere with `TEST_DATABASE_URL`.

## Layout

```text
backend/src/lucid/
  api/           HTTP routes, request/response schemas
  application/   orchestration, context budgeting, attempt lifecycle
  domain/        provider protocol, events, error taxonomy
  persistence/   engine, models, repositories
  providers/     gemini adapter, fake provider
backend/migrations/  Alembic revisions
frontend/src/    React application
docs/            specs, plan, ADRs
```

## Repository and publishing

The repository is named `lucid`. Nothing is published yet, so CI has never run.
To create the GitHub remote:

```powershell
gh repo create lucid --private --source . --remote origin --push
```

Flip it to public when the MVP is demonstrable and the README, mockups, and
architecture notes are in place.

## Known limitations (by design, for now)

- No authentication or multi-user support. Do not expose this beyond localhost.
- Single backend process: generation tracking is in-process.
- No conversation summarization; long conversations lose their oldest turns
  from the model's context (the data is still stored).
- Model is fixed by configuration; there is no model picker yet.
- Partial assistant text is not checkpointed, so a hard crash loses that tail.

## Data handling

Use only synthetic, non-sensitive content. Free-tier provider traffic may be used
to improve the provider's products. Requests are sent with `store=false` so no
provider-side interaction state is retained beyond the request.
