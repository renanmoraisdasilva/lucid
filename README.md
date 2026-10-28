# Chatbot MVP

A single-user, ChatGPT-style chatbot built as a learning project: FastAPI +
PostgreSQL backend, React + TypeScript frontend, streamed responses from Gemini.

The point is not the chatbot. It is to build, test, and explain the complete
lifecycle of an LLM-backed application — request, context construction, provider
streaming, persistence, cancellation, failure handling, and observability —
without hiding behind a framework or an agent library.

## Status

**Design complete, implementation not started.**

The specification is approved and all open design decisions are resolved. Code
begins with Milestone 1 of the implementation plan. Nothing in this repository
runs yet, and the quickstart below is written for Milestone 1.

## Documentation

| Document | Purpose |
|---|---|
| [`docs/specs/001-chatbot-mvp-specification.md`](docs/specs/001-chatbot-mvp-specification.md) | What the system must do: scope, non-goals, UX, data model, acceptance criteria |
| [`docs/plans/implementation-plan.md`](docs/plans/implementation-plan.md) | How it gets built: architecture, DDL, API and SSE contracts, milestones, tests, risks |
| [`docs/decisions/`](docs/decisions/) | ADRs for the consequential choices (provider, data model, streaming, ids, failures, frontend) |

Read the specification first, then the plan. The ADRs explain the decisions that
the spec leaves as outcomes rather than reasoning.

## Scope in one paragraph

One user, no authentication. Send a message, watch the reply stream in, stop it
mid-flight, retry a failure, browse and delete conversations, read Markdown with
syntax-highlighted code blocks. Everything persists in PostgreSQL. Full
conversations are stored; only a bounded, budgeted slice is sent to the model.
No RAG, no agents, no tools, no file uploads, no cloud deployment.

## Planned stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic v2 |
| Persistence | PostgreSQL 17, SQLAlchemy 2.x async, asyncpg, Alembic |
| Model | Gemini `gemini-3.5-flash-lite` via the Interactions API (`google-genai`) |
| Streaming | Server-Sent Events over `POST`, parsed with `fetch` |
| Frontend | React 19 + TypeScript, Vite, Tailwind CSS, TanStack Query |
| Quality | Ruff, Pyright, pytest, ESLint, Vitest, GitHub Actions |
| Local dev | PostgreSQL in Docker Compose; app processes on the host |

## Quickstart (target, from Milestone 1)

```powershell
# 1. Start PostgreSQL
docker compose up -d db

# 2. Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn chatbot.main:app --reload

# 3. Frontend (second terminal)
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` before talking to the
model. Without it, set `PROVIDER=fake` to run against the scripted fake provider.

## Prerequisites

- Docker Desktop with Compose v2+
- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/) — **not currently installed
  on the development machine**
- Node.js 22+
- A Gemini API key (free tier is sufficient)

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
