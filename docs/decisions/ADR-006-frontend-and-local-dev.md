# ADR-006 — Frontend stack and local development layout

- **Status:** Accepted
- **Date:** 2026-10-28
- **Deciders:** Renan Silva (with AI assistant)
- **Related:** ADR-003

## Context

The specification had no frontend decisions at all: no styling approach, no
Markdown renderer, no data-fetching strategy. It also left the local
Docker Compose layout open. Both matter because they shape daily iteration speed
and the amount of code we hand-roll versus adopt.

Environment facts that informed this:

- Windows host, PowerShell, Node 22 and Docker Desktop 29 present.
- **Python and `uv` are not installed**, and there is no Linux distro in WSL
  (only the Docker Desktop distro).
- Bind-mounted Python containers on Windows make edit-reload loops noticeably
  slower.

## Decision

### Frontend

- **Vite + React + TypeScript (strict)** — no meta-framework. Next.js would add a
  server runtime that this project does not need and would blur the
  frontend/backend split the roadmap wants to teach.
- **Tailwind CSS** for layout and styling.
- **Markdown:** `react-markdown` + `remark-gfm` + `rehype-sanitize` +
  `rehype-highlight`, with a per-code-block copy button.
- **Server state:** TanStack Query (`useInfiniteQuery` for the sidebar,
  `useQuery` for a conversation).
- **Streaming:** `fetch` + `ReadableStream` with a small SSE frame parser
  (ADR-003). `EventSource` is not used.
- **Tests:** Vitest + React Testing Library, with a `fetch` mock that replays
  recorded SSE frames.

### Local development

- **PostgreSQL runs in Docker Compose.** Always.
- **Backend and frontend run on the host** (`uv run uvicorn ... --reload`,
  `npm run dev`), with Vite proxying `/api` to the backend.
- A **full-stack Compose profile** (`docker compose --profile full up`) exists
  only to verify the acceptance criterion "a developer can start everything from
  the documented steps". It is not the primary loop.
- CI runs on GitHub Actions from Milestone 1.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Hand-rolled CSS modules, `marked` + `DOMPurify`, no data library | Fewer dependencies, but re-implements caching, invalidation, and sanitization plumbing — time better spent on the AI-facing code. |
| Next.js + component library (shadcn/ui) | Polished fastest, but adds a server runtime with no role in this architecture and hides the HTTP contract the project is meant to teach. |
| Everything in Compose with hot reload | Closest to shipped behaviour, but Windows bind-mount watching makes the tight iteration loop painful, and debugging inside containers from day one teaches the wrong lesson first. |
| Backend in Compose, frontend local | Pays container overhead for the code with the most iteration. |
| Local-only CI (pre-commit hook) | No Postgres integration tests in the pipeline and nothing a reviewer can see. |

## Consequences

**Positive**

- Sub-second reload for both processes; failures point at real stack traces, not
  container plumbing.
- Markdown is sanitized by a maintained plugin chain rather than bespoke regexes.
- The frontend is a static bundle with no server component, which keeps the
  deployment story trivial later.

**Negative / accepted costs**

- Two terminals plus Docker for Postgres. Mitigated with documented npm scripts
  (`npm run dev:api`, `npm run dev:web`) and a README quickstart.
- The full-stack Compose path can drift from host development. Mitigated by
  running it once per milestone and at acceptance.
- Tailwind and the Markdown plugin chain are dependencies to justify; each is
  documented in the README's dependency table.
- The sanitize schema is intentionally restrictive; some legitimate HTML will be
  stripped. That is the correct default for model output.

## Follow-ups

- Add `docker compose --profile full` verification to the acceptance checklist
  and to CI only if it stays fast.
