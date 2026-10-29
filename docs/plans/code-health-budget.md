# Code health budget

**Status:** Active from 2026-10-29
**Scope:** all backend and frontend source in `chatbot_mvp/`
**Related:** [implementation plan](./implementation-plan.md), [dashboard plan](./dashboard-implementation-plan.md)

## 1. Why this exists

The MVP was about 4,900 lines of source and 4,000 lines of tests before this
budget. The dashboard adds roughly another 2,500 source lines (seven metrics,
three chart families, a recent-attempts table, a details modal, aggregation
queries, pricing and retention). Without a budget, the most likely outcome is a
585-line `chat_service.py`, a 600-line `DashboardPage.tsx`, and a single SQL query
that nobody wants to change.

This document sets the limits before the dashboard is written, and records the
refactors that must happen first. It is deliberately concrete: a number, a tool,
and a command.

## 2. Baseline (2026-10-29)

Measured with physical lines (blanks included) from `HEAD` on 2026-10-29; radon
provided complexity and MI. Coverage was not configured at that point, so the
baseline has no coverage column.

| Area | Files | Lines |
|---|---:|---:|
| Backend source (`backend/src/lucid`) | 37 | 3,237 |
| Backend tests (`backend/tests`) | 30 | 3,248 |
| Migrations | 3 | 201 |
| Frontend source (`frontend/src`, no tests) | 16 | 1,653 |
| Frontend tests (`*.test.ts[x]`) | 7 | 737 |

**Current hot spots**

| File | Lines | Problem |
|---|---:|---|
| `application/chat_service.py` | 585 | `stream_generation` is 164 lines and radon CC **22 (grade D)**; `_stream_with_retries` is CC **14 (grade C)**; MI 33.99 (warning band) |
| `persistence/repositories.py` | 253 | three repositories in one module; MI 33.76 (warning band) |
| `hooks/useChat.ts` | 312 | query state, stream lifecycle and mutations in one hook |
| `components/MessageList.tsx` | 258 | user, assistant and streaming rendering in one component |
| `providers/gemini.py` | 309 | at the provider warning line; mapping and transport in one module |

**Complexity and maintainability snapshot** (`radon`, 2026-10-29, 200 blocks):

| Metric | Value |
|---|---|
| Average cyclomatic complexity | A (2.39) |
| Functions above the proposed CC 12 limit | 2: `stream_generation` (22), `_stream_with_retries` (14) |
| Functions in the CC warning band (9–12) | `prepare_retry` (9), `select_history` (9), `read_conversation` (9) |
| Files below the MI 40 warning | `chat_service.py` (33.99), `repositories.py` (33.76) |
| Files below the MI 30 fail | none |
| Functions over 50 lines | 4, all in `chat_service.py` |

The codebase is healthy on average; the failure is concentrated in one orchestration
file. That is exactly the file the dashboard will grow, so the refactor is not
optional.

No coverage threshold, file-size rule or complexity rule exists today. CI runs
ruff, pyright, pytest, ESLint, `tsc` and Vitest only.

## 3. Limits

File sizes are **physical lines**, blanks and comments included. That is the
number that makes a file hard to hold in your head; SLOC is used only by the
maintainability index.

### 3.1 File size

| Kind | Warning | Fail | Notes |
|---|---:|---:|---|
| Python module (`domain`, `application`, `api`, `persistence`) | 250 | 300 | split by responsibility, not by line count alone |
| Python provider adapter | 300 | 350 | adapters are allowed more room for mapping |
| Python test module | 500 | 600 | cases accumulate; still capped |
| Alembic migration | — | — | exempt, generated history |
| `persistence/tables.py`, `config.py` | — | — | exempt, declarative/wiring |
| TS/TSX component | 150 | 200 | one visual responsibility per file |
| TS hook, page or service | 120 | 180 | orchestration only; extract pure logic to `lib/` |
| TS/TSX `lib` or API module | 150 | 200 | |
| TS/TSX test module | 300 | 400 | |
| CSS | 200 | 250 | |

### 3.2 Functions, nesting and complexity

| Check | Warning | Fail | Applies to |
|---|---:|---:|---|
| Function length | 40 | 50 | Python source and TS `lib`/`api`; tests 60 / 80; TSX components and hooks are governed by the file cap and complexity |
| Nesting depth | 3 | 4 | control-flow nesting |
| Parameters | 4 | 5 | source logic; framework handlers and test harnesses are exempt |
| Cyclomatic complexity | 9 | 12 | radon `cc` for Python source, ESLint `complexity` for TS; test modules exempt |

Components and hooks are not forced under the 50-line function cap: JSX and query
composition are not linear code. Their file cap and per-function complexity are the
guardrails, and the review checks whether a component has one visual responsibility.

Do not satisfy the limit by extracting a `utils.ts` or `helpers.py` grab bag.
Extract with a name that describes the responsibility (`pricing.py`,
`chart-geometry.ts`).

### 3.3 Maintainability index

Python files are measured with radon's Maintainability Index (0–100). It combines
Halstead volume, cyclomatic complexity and size, so it naturally penalises large
files.

| Check | Warning | Fail |
|---|---:|---:|
| File MI | below 40 | below 30 |

MI is experimental and absolute values depend on comments and file size. It is a
tripwire, not a grade. It applies to source modules only; test modules are exempt.
TypeScript has no equivalent tool worth trusting; the ESLint size and complexity
rules above are the TypeScript proxy.

### 3.4 Coverage

Coverage is measured with branch coverage.

| Layer | Target |
|---|---:|
| Backend overall | 80% |
| `domain` + `application` | 90% |
| `persistence` | 85% |
| `providers` | 85% |
| `api` | 80% |
| Frontend overall | 75% |
| `lib` + `api` | 90% |
| `hooks` | 85% |
| `components` + `pages` | 70% |

The **hard CI gate is the overall floor** (80 backend, 75 frontend). The layer
numbers in the table are line-coverage targets and are reported at every milestone;
branch coverage is reported next to them, and the global gate uses branch-aware
totals. A layer below target needs a reason in the health report, not a silent pass.

Coverage is a floor, not a goal. These paths require explicit tests regardless of
the total:

- SSE terminal-event handling: exactly one `done`/`error`, stop and disconnect.
- Automatic retry counting and eligibility.
- Attempt terminal-state transitions.
- Dashboard aggregation boundaries: empty range, exact start/end, in-progress
  exclusion, missing usage, missing pricing, retry counting.
- Telemetry retention: deletes only old terminal attempts, never conversations or
  messages.
- Pagination cursor round-trip and stable ordering.

Exclusions: Alembic migrations, `src/test`, `main.tsx`, generated type-only
modules, and build/config files.

### 3.5 Import boundaries

The existing `backend/tests/test_import_boundary.py` is the guard; extend it rather
than adding `import-linter`.

- `domain` imports nothing from `application`, `persistence`, `providers` or `api`.
- `providers` imports only `domain` (plus third-party SDKs).
- `persistence` imports only `domain` and SQLAlchemy.
- `api` imports `application`, `domain` and its own schemas; never `providers` or
  `persistence` directly.
- `application` may import `domain`, `persistence` and `providers` contracts
  through injected interfaces, never concrete Gemini SDK types.

Frontend direction: `pages` → `components`/`hooks`; `hooks` → `api`/`lib`;
`components` → `lib`; `lib` imports no React, hooks, components or API modules.
No module cycles. Review this in the PR until an automated check is justified.

## 4. Measurement and reporting

### 4.1 Commands

Backend, from `backend/`:

```powershell
uv run pytest -q --cov=lucid --cov-branch --cov-report=term-missing --cov-report=json
uv run radon cc src -s -a
uv run radon mi src -s
```

Frontend, from `frontend/`:

```powershell
npm run test:coverage
npm run lint
```

A single file-size scan, from the repo root:

```powershell
Get-ChildItem backend\src,frontend\src -Recurse -File |
  Where-Object { $_.Extension -in '.py','.ts','.tsx','.css' } |
  ForEach-Object { [pscustomobject]@{ Lines = (Get-Content $_.FullName).Count; Path = $_.FullName } } |
  Sort-Object Lines -Descending | Select-Object -First 20
```

### 4.2 CI gates

Add these to the existing workflow:

| Job | Gate |
|---|---|
| Backend | `pytest --cov-fail-under=80` with branch coverage; `tests/test_code_health.py` checks file size, function size, nesting, parameters, complexity and MI |
| Backend | `radon cc` / `radon mi` output retained as a CI artifact or log |
| Frontend | ESLint `max-lines`, `max-lines-per-function`, `complexity`, `max-depth`, `max-params`; test files override the caps |
| Frontend | `vitest --coverage` with 75% lines/statements, 70% branches/functions |

`tests/test_code_health.py` is a small stdlib + radon test over `src/lucid` and
`backend/tests`, using the source and test caps separately. It starts as a failing
test for the current hot spots; the refactor in §5 makes it green. No grandfather
file is kept after that refactor.

### 4.3 Health report

At the end of every milestone, add a section to the milestone note or PR:

```markdown
## Health report — <milestone>

| Area | Files | Source lines | Test lines | Coverage | Largest file | Longest fn | Max CC | Min MI |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| backend/domain | | | | | | | | |
| backend/application | | | | | | | | |
| backend/persistence | | | | | | | | |
| backend/providers | | | | | | | | |
| backend/api | | | | | | | | |
| frontend/lib+api | | | | | | | | |
| frontend/hooks | | | | | | | | |
| frontend/components+pages | | | | | | | | |

Violations: none
Waivers: none
Largest new file: <path> (<lines>)
```

Attach the full per-file line-count scan next to the summary table. The table is the
trend; the scan is the detail.

### D0 health report (2026-10-29)

| Area | Files | Source lines | Test lines | Line cov. | Branch cov. | Largest file |
|---|---:|---:|---:|---:|---:|---|
| backend/domain | 6 | 246 | — | 99.2% | n/a | `errors.py` 87 |
| backend/application | 15 | 1,290 | — | 94.0% | 75.8% | `chat/streaming.py` 260 |
| backend/persistence | 8 | 529 | — | 86.7% | 50.0% | `tables.py` 137 |
| backend/providers | 5 | 436 | — | 91.4% | 88.2% | `gemini.py` 309 |
| backend/api | 8 | 693 | — | 85.9% | 42.9% | `routes_chat.py` 198 |
| backend/root | 4 | 257 | — | — | — | `main.py` 76 |
| frontend/lib+api | 6 | 337 | — | 98.9% | 92.0% | `client.ts` 109 |
| frontend/hooks | 4 | 385 | — | 84.8% | 65.0% | `useChatStream.ts` 186 |
| frontend/components | 11 | 771 | — | 83.0% | 79.4% | `Sidebar.tsx` 140 |
| frontend/shell | 3 | 125 | — | — | — | `App.tsx` 95 |
| **Totals** | **69 source** | **5,069** | **4,564** | **88.6 / 87.4** | **74.4 / 78.3** | `gemini.py` 309 |

- Violations: none. Both coverage floors pass; the health test passes.
- Warnings: frontend hooks are 84.8% line coverage against an 85% target.
- Min MI 42.00; max CC 9; no C, D, E or F function grades.
- The refactor added 214 backend source lines for module boundaries and removed
  35 frontend source lines; tests grew by 147 backend and 432 frontend lines.
- All public HTTP/SSE contracts are unchanged; 204 backend and 63 frontend tests pass.

### D1 health report (2026-10-29)

- Backend: 206 tests, 3,589 source + 3,464 test lines, **89.0% coverage** (75.2% branches), no C–F functions, minimum MI 42.00.
- Frontend: unchanged at 63 tests, 1,618 source + 1,169 test lines, 87.4% lines / 78.3% branches.
- New backend files: `chat/telemetry.py` (25), `chat/events.py` (90), migration 0003 (72). Net +138 source lines.
- Violations: none. The new fields are metadata only; no prompts or message bodies entered telemetry.

### D2 health report (2026-10-29)

- Backend: 216 tests, 3,730 source + 3,676 test lines, **89.0% coverage** (75.4% branches), no C–F functions, minimum MI 42.00.
- New files: `dashboard/pricing.py` (56 lines, 100% covered) and `dashboard/retention.py` (59 lines, 92%).
- Frontend unchanged at 63 tests, 1,618 source + 1,169 test lines, 87.4% lines / 78.3% branches.
- Warning: the startup/24-hour wiring in `main.py` is verified by the retention function tests and the startup checklist, not by a lifespan unit test.
- Violations: none.

The report is the answer to "is this getting out of hand?" If a number moves the
wrong way, the milestone is not done until it is explained or fixed.

## 5. Refactor before dashboard work

Roughly one and a half to two days. Do it as separate, reviewable commits with no
behaviour change, then turn the gates on.

### 5.1 Backend

`application/chat_service.py` becomes a package:

| File | Responsibility | Estimated lines |
|---|---|---:|
| `application/chat/__init__.py` | public chat API | 25 |
| `application/chat/options.py` | `GenerationOptions` | 20 |
| `application/chat/turns.py` | `PreparedGeneration`, `prepare_message`, `prepare_retry`, errors | 171 |
| `application/chat/streaming.py` | `stream_generation`, event mapping, terminal events | 260 |
| `application/chat/retries.py` | bounded provider stream, retry decision, stop-aware sleep | 168 |
| `application/chat/finalize.py` | terminal transaction, cancellation finalizer | 120 |

`stream_generation` is split so no function exceeds 50 lines or CC 12: open the
provider stream, consume events, decide retry eligibility, finalize success,
finalize failure, finalize interruption. Retry decisions and backoff move into a
small helper. The public chat functions and SSE payloads stay identical.

`persistence/repositories.py` is split by aggregate, keeping package-level exports
so existing imports do not change:

| File | Responsibility | Lines |
|---|---|---:|
| `persistence/repositories/__init__.py` | re-export the three repositories | 10 |
| `persistence/repositories/conversations.py` | conversation CRUD and pagination | 78 |
| `persistence/repositories/messages.py` | message append, sequence, read | 64 |
| `persistence/repositories/attempts.py` | attempt lifecycle and lookups | 126 |

This also gives the dashboard queries an obvious sibling module instead of growing
the repository file.

### 5.2 Frontend

| File | Responsibility | Lines |
|---|---|---:|
| `hooks/useChat.ts` | queries, mutations, public controller | 136 |
| `hooks/chat/useChatStream.ts` | SSE lifecycle, optimistic state, abort | 186 |
| `hooks/chat/stream-events.ts` | pure event folding and controller type | 50 |
| `hooks/chat/chat-error.ts` | error normalization and abort detection | 22 |
| `components/MessageList.tsx` | list composition and scrolling | 95 |
| `components/chat/UserTurn.tsx` | user bubble, timestamp, retry | 50 |
| `components/chat/AssistantTurn.tsx` | avatar, usage row, status, markdown | 55 |
| `components/chat/StreamingTurn.tsx` | streaming article and waiting indicator | 45 |
| `components/chat/ErrorNotice.tsx` | error card and cool-down retry | 75 |
| `components/chat/failure-text.ts` | sanitized failure explanations | 28 |

No reducer was introduced: the state was small, and extracting the pure event
fold plus the error normalizer removed the branching without adding indirection.
Add the reducer only if the dashboard or a future feature shares transcript state.

### 5.3 Exit criteria

- `stream_generation` ≤ 50 lines and ≤ 12 CC; every source file below its fail limit.
- Public chat functions and all HTTP/SSE contracts unchanged.
- Existing backend and frontend tests pass, plus new stream, chart-free UI and API client tests.
- Coverage floors met (80 backend / 75 frontend); actual 88.6 / 87.4 lines.
- `radon cc` maximum ≤ 12 and minimum MI ≥ 40 across source (current minimum 42.00).
- The dashboard plan starts from a green health report.

**Completed 2026-10-29.** The D0 report is below.

### 5.4 Effort

| Task | Estimate |
|---|---:|
| Add tooling, coverage config and `test_code_health.py` | 0.25 day |
| Backend split (chat package + repositories) and characterization tests | 0.75 day |
| Frontend split + reducer tests | 0.5 day |
| Fix findings from the first full report | 0.25 day |

## 6. Exceptions

An exception is a line in this document, not an inline disable:

- why the file or function genuinely cannot be split;
- the measured size/complexity;
- an expiry milestone.

`# noqa` and `eslint-disable` need a comment on the same line and a linked issue
or note here. A second exception for the same reason means the budget or the
design is wrong; revisit the budget rather than normalising the exception.

## 7. What is not enforced

- Naming, docstrings, comment density and test-to-source ratio are review
  guidelines. Coverage and size are already proxies; adding more numbers would
  optimise the numbers instead of the design.
- Mutation testing, dead-code detection and dependency-cruiser are deferred. Add
  them only if a real defect class slips through.
- Generated code, migrations and declarative table modules are exempt from size
  limits by design.

## 8. Notes on the readability index

The Maintainability Index is the closest thing to a readability score that
exists, and it is only meaningful per language and per file. It is useful for
spotting a file that has become a dumping ground; it is not a target to maximise
by adding comments. TypeScript has no trustworthy equivalent, so do not compare
MI numbers across the two stacks or invent a combined score.
