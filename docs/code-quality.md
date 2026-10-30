# Code quality

The quality gates are not there to look strict. Each one exists because something went wrong without it, or because a specific file was about to become unmaintainable. This page lists the gates, the budgets, and the refactors they forced.

## The gates

| Gate | Tool | Setting | Fails the build |
| --- | --- | --- | --- |
| Python lint | Ruff | default rules + 100-column lines | yes |
| Python format | Ruff format | — | yes |
| Python types | Pyright | `strict` | yes |
| Python tests | pytest | `--cov-fail-under=80` | yes |
| DB migrations | Alembic | `upgrade head` on a real PostgreSQL | yes |
| JS/TS lint | ESLint | complexity, size, depth, params | yes |
| JS/TS format | Prettier | — | yes |
| TS types | `tsc --noEmit` | `strict` | yes |
| Frontend tests | Vitest + coverage | 75 % lines/statements, 70 % branches/functions | yes |
| Frontend build | Vite | production build | yes |

Both jobs run on every push to `main` and every pull request. The full backend job also prints a Radon complexity and maintainability report, so drift is visible even when it is under the limit.

**Zero suppressions in application code.** There is no `# type: ignore` and no `# noqa` anywhere under `backend/src`. When the strict checker complained, the code changed.

## Budgets, enforced by a test

`backend/tests/test_code_health.py` parses the source with `ast` and fails on:

| Rule | Limit |
| --- | --- |
| Source file | 300 lines (350 for provider adapters, 600 for tests) |
| Function | 50 lines (80 for tests) |
| Parameters | 5 |
| Nesting depth | 4 |
| Cyclomatic complexity | 12 |

ESLint enforces the same idea on the frontend: **200 lines per component**, **400 per test file**, complexity 12, nesting 4, 5 parameters, and 50 lines per function in `src/lib` and `src/api`.

These numbers are documented, with the reasoning and the baseline measurement, in [`plans/code-health-budget.md`](plans/code-health-budget.md). The short version: the MVP was about 4,900 source lines, the dashboard was about to add 2,500 more, and the budget was set **before** the dashboard was written.

## What the budget actually forced

The budget was written against a real measurement, and it named the offenders in advance. All of them were refactored before the dashboard landed:

| Before | Problem | After |
| --- | --- | --- |
| `application/chat_service.py` (585 lines) | `stream_generation` was 164 lines, complexity **22 (grade D)**; four functions over 50 lines | `application/chat/` — `turns`, `streaming`, `finalize`, `events`, `retries`, `telemetry`, `options` |
| `persistence/repositories.py` (253 lines) | three repositories in one module, maintainability index in the warning band | `persistence/repositories/` — one module per aggregate |
| `hooks/useChat.ts` (312 lines) | query state, stream lifecycle and mutations in one hook | `useChat` (list + selection) + `hooks/chat/useChatStream`, `stream-events`, `chat-error` |
| `components/MessageList.tsx` (258 lines) | user, assistant and streaming rendering in one file | `components/chat/` — `UserTurn`, `AssistantTurn`, `StreamingTurn`, `ErrorNotice` |
| `providers/gemini.py` (309 lines) | mapping and transport together, at the provider warning line | `providers/streams.py` plus a thinner adapter |

The second provider and the picker were held to the same rules once they existed:

- The OpenAI-compatible adapter's `stream` method hit 52 lines → payload building and SSE line parsing were extracted into `_payload()` and a small `_StreamState`.
- The picker's first version was 221 lines with complexity 17 → split into `ModelPicker` (state), `ModelPickerTrigger`, `ModelPickerList`, `useModelPickerKeys`, `useCollapseWhenDisabled`, and a pure `model-label` helper.
- `retry_message_endpoint` grew to 7 parameters → the streaming dependencies were bundled into one `StreamDeps` object.

None of these refactors changed behaviour; the tests were already there to prove it.

## Boundaries, not conventions

Two tests protect structure that a code review would otherwise have to remember:

- **`tests/test_import_boundary.py`** — the domain layer must not import provider adapters, persistence, or SQLAlchemy, and persistence must not import providers. The provider boundary is a fact of the build, not a guideline.
- **`tests/test_code_health.py`** — the size and complexity limits above.

The same idea appears in the TypeScript: `hooks/chat/` owns the stream, `api/` owns transport, `components/chat/` owns rendering. Each has one reason to change.

## Where the tests stop and review starts

Gates cannot judge naming, UX copy, or whether a diagram is true. They also cannot prove a chart looks right — only that it receives the right numbers. Those are what the screenshots and the E2E pass are for.

## Run the gates

```powershell
# Backend, from backend/
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q --cov=lucid --cov-branch --cov-fail-under=80

# Frontend, from frontend/
npm run lint
npm run format:check
npm run typecheck
npm run test:coverage
npm run build
```
