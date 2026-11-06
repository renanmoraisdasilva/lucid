# Lucid — Agent Guide

Lucid is a single-user AI chat app: FastAPI backend, React frontend, PostgreSQL,
and streamed provider responses. Tests and docs are part of the deliverable.

## Read first

- `README.md` — what it is and how to run it.
- `docs/README.md` — the documentation map.
- `docs/features/` — current behavior rules.
- `docs/decisions/` — why the system is shaped this way.
- `docs/testing.md` — test layers, commands, coverage, and quality gates.

## Documentation map

| Question | Document |
| --- | --- |
| Product, setup, run | `README.md` |
| How agents work here | `AGENTS.md` |
| Current behavior | `docs/features/` |
| Why we chose it | `docs/decisions/` (ADRs) |
| How it is put together | `docs/architecture.md` |
| How to test and verify | `docs/testing.md` |
| Active future work | `docs/plans/` — create only while active |
| Deployment and runbooks | `docs/operations.md` — only if operated |
| Superseded material | `docs/archive/` — history, never current truth |
| Design mockups | `ui-mockups/` |
| Images and demo media | `assets/` |

Rules:

- One question, one file. Link instead of duplicating.
- Implemented behavior lives in `docs/features/`, not in specs.
- A feature document may contain as many rules as the capability needs. There is
  no maximum rule count; split only when a document becomes hard to read.
- Decisions live in ADRs; deferred work lives in `docs/plans/`.
- Do not keep a completed spec or plan as a second source of current behavior.
  Archive it or delete it.

## Behavior workflow

1. Find the rule with `npx trace-docs context <ID>`.
2. Read the rule and its linked ADR.
3. Change the code and the rule together.
4. Put the rule ID in the proving test name, or in a comment for pytest.
5. Run `npm run trace:verify`.
6. Generate evidence when needed: `npm run trace:evidence`.

`trace:verify` is also a real test:

- `frontend/src/traceability.test.ts`
- `backend/tests/unit/test_traceability.py`

A normal test run fails when code or tests change without the affected rule
document changing.

Trace Docs is installed from `tools/trace-docs-0.4.1.tgz` into `node_modules`.
There is no sibling-path reference and no npm publish.

## Commands

```powershell
# From the repository root
npm install
npm run dev

npm run trace:evidence
npm run trace:check
npm run trace:verify

# Backend
node tools/uv.mjs run pytest tests/unit
node tools/uv.mjs run ruff check .
node tools/uv.mjs run pyright

# Frontend
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run typecheck
```

## Boundaries

- Domain code must not import provider adapters, persistence, or SQLAlchemy.
- Persistence must not import providers.
- `frontend/src/api/` owns transport; `hooks/chat/` owns the stream; `components/chat/` owns rendering.
- No suppressions in application code.
- Size and complexity budgets are enforced by tests, not review memory.

## Documentation standard for future projects

Minimum:

```text
README.md
AGENTS.md
docs/features/
docs/decisions/
```

Add when needed:

```text
docs/README.md          # map, when docs grow beyond a handful
docs/testing.md         # when there are tests
docs/architecture.md    # when the system has several moving parts
docs/plans/             # only while a plan is active
docs/operations.md      # only if deployed
docs/archive/           # only if history is worth keeping
ui-mockups/             # design artifacts, outside docs
assets/                 # images and demo media, outside docs
```

Do not create a separate `specs/`, `architecture/`, `code-quality.md`, or
`how-it-was-built.md` by default. Those are either current behavior (features),
current structure (architecture), quality gates (testing), or history (archive).
