# Chatbot MVP — Product & Technical Specification

**Status:** Approved for implementation  
**Version:** 0.2  
**Last updated:** 2026-10-28

> This specification records the decisions made during the interview. Items marked
> **Proposed** or **Open** are not yet confirmed requirements. Checkboxes are
> intended to track implementation and acceptance.
>
> **v0.2 (2026-10-28):** All open decisions from v0.1 were resolved in a second
> interview round. Section 15 now lists the resolved decisions, the concrete
> schema and API/SSE contract live in
> [`../plans/implementation-plan.md`](../plans/implementation-plan.md), and the
> consequential decisions are recorded as ADRs in `../decisions/`.
> Implementation follows the plan's milestones.

## 1. Purpose

Build a single-user, general-purpose chatbot with a ChatGPT-like interface. The project is a learning-focused AI engineering application: it should demonstrate sound application architecture, LLM integration, streaming, persistence, error handling, and testing without expanding into RAG, agents, or other advanced capabilities.

The first version will run locally through Docker Compose.

## 2. Goals

- [ ] Provide a usable chat interface for sending messages and receiving AI responses.
- [ ] Integrate Gemini as the initial LLM provider.
- [ ] Stream responses to the browser from the beginning.
- [ ] Persist conversations, messages, and generation attempts in PostgreSQL.
- [ ] Handle provider failures and interrupted streams predictably.
- [ ] Keep the application code independent of Gemini-specific SDK details through a small provider boundary.
- [ ] Make the project easy to run locally using Docker Compose.
- [ ] Keep the implementation understandable and appropriately scoped for learning.

## 3. Non-goals and out of scope

The following are explicitly not part of the chatbot MVP:

- [ ] Authentication, registration, or multi-user support.
- [ ] RAG, document ingestion, embeddings, vector search, or citations.
- [ ] Tool/function calling, agents, or external actions.
- [ ] File uploads, image input, audio, or voice.
- [ ] Multiple model providers or provider fallback.
- [ ] User-selectable models or generation parameters.
- [ ] Editing previous user messages.
- [ ] Regenerating assistant responses.
- [ ] Queuing multiple messages while a response is running.
- [ ] Conversation search.
- [ ] Full-conversation export/copy.
- [ ] Conversation archive functionality.
- [ ] Cloud deployment.
- [ ] Admin interface or runtime system-prompt editor.
- [ ] Circuit breakers or advanced resilience patterns.

These features may be considered in later projects or iterations, but should not be introduced into the MVP without an explicit scope decision.

## 4. Users and operating assumptions

### Confirmed decisions

- **User model:** One user only.
- **Authentication:** None in the MVP.
- **Deployment:** Local development environment using Docker Compose.
- **Frontend:** React + TypeScript.
- **Backend:** Python + FastAPI.
- **Database:** PostgreSQL.
- **LLM provider:** Gemini, configured on the backend.
- **System prompt:** Stored in a backend configuration file and version-controlled.
- **Conversation history:** Persistent.
- **Conversation creation:** A conversation is created only when its first user message is submitted. Clicking “New chat” alone does not create a database record.

### Constraints

- Use synthetic or non-sensitive content. Do not send secrets, personal information, or confidential data to the free-tier model service.
- Keep provider credentials on the backend. Never expose the Gemini API key to the browser.
- Prefer hosted inference for this project; do not require a local model to run continuously.
- Avoid unnecessary paid services and cloud infrastructure during the MVP.

## 5. User experience and functional requirements

### 5.1 Main chat interface

- [ ] ChatGPT-like layout with a sidebar and main conversation area.
- [ ] Sidebar includes a **New chat** action.
- [ ] Sidebar lists saved conversations, newest/recently updated first.
- [ ] Main area displays user and assistant message bubbles.
- [ ] Message composer supports sending a message.
- [ ] While a response is generating, disable the composer and prevent another message from being submitted.
- [ ] Provide a **Stop** action while a response is generating.
- [ ] Show a clear loading/generating state.
- [ ] Display errors in a clear, user-understandable way.
- [ ] Preserve and display interrupted assistant text when generation is stopped or interrupted.

### 5.2 Markdown and code rendering

- [ ] Render assistant responses as Markdown.
- [ ] Support headings, paragraphs, lists, links, tables, inline code, and fenced code blocks.
- [ ] Provide syntax highlighting for code blocks.
- [ ] Provide a copy button for each code block.
- [ ] Sanitize rendered Markdown/HTML and restrict unsafe links or embedded content.
- [ ] Do not add full-conversation copy/export in the MVP.

### 5.3 Conversations

- [ ] Create a conversation when the first user message is submitted.
- [ ] Persist conversation history in PostgreSQL.
- [ ] Allow the user to open an existing conversation.
- [ ] Allow the user to continue an existing conversation.
- [ ] Allow the user to start a new conversation.
- [ ] Allow permanent deletion of a conversation and its associated messages/attempts.
- [ ] Do not implement archive functionality.
- [ ] Show conversations newest/recently updated first.
- [ ] Use pagination to load the conversation list, fetching older entries as needed.
- [ ] Do not implement conversation search.
- [ ] Generate the initial conversation title deterministically from the first user message; do not make an additional Gemini call for title generation.
- [ ] Store the full generated title and truncate it only in the sidebar UI.
- [ ] **Resolved (v0.2):** Apply a maximum title length of **80 Unicode code points** when saving. Normalize whitespace, collapse runs, trim, then cut at the last space inside the final 20 code points when that avoids a mid-word cut; otherwise hard-cut at 80. Fall back to `New chat` if the message normalizes to empty. The sidebar additionally truncates visually with CSS ellipsis.

### 5.4 Model configuration

- [ ] Use one Gemini model configured on the backend.
- [ ] Do not expose a model selector in the UI.
- [ ] Do not expose temperature or other generation controls in the UI.
- [ ] Keep model name and generation settings in backend configuration.
- [ ] Keep the system prompt in a separate, version-controlled backend configuration file.
- [ ] Do not build a database-managed prompt editor.

### 5.5 Streaming and cancellation

- [ ] Stream assistant output from the beginning using Server-Sent Events (SSE).
- [ ] Send incremental text to the browser as it becomes available.
- [ ] Define explicit stream event types for text deltas, completion, and errors.
- [ ] **Resolved (v0.2):** Event names and payloads are `meta`, `delta`, `usage`, `done`, and `error`, defined in the implementation plan. A terminal `done` or `error` event always ends the stream, followed by connection close.
- [ ] **Resolved (v0.2):** The browser POSTs the message and parses the `text/event-stream` response from `fetch` + `ReadableStream`. `EventSource` is not used because it cannot send a request body.
- [ ] Persist the user message before starting provider generation.
- [ ] Persist assistant output as it is generated or otherwise ensure received partial output can be recovered and saved when the stream ends.
- [ ] Allow the user to stop generation.
- [ ] On stop, attempt to cancel the provider request and preserve received text as an `interrupted` assistant generation attempt.
- [ ] If the browser refreshes or disconnects during generation, cancel the generation and preserve received text as interrupted.
- [ ] Account for the possibility that provider-side cancellation is not immediate or cannot be guaranteed.
- [ ] **Resolved (v0.2):** Cancellation is implemented by cancelling the asyncio task consuming the provider stream and closing the stream. The Interactions API `cancel(id)` is only available for background interactions, which the MVP does not use, so the provider may finish generating server-side after our cancellation. This is accepted and documented rather than worked around.
- [ ] Do not allow a second message to be submitted while the current response is generating.
- [ ] Do not queue messages.
- [ ] Do not support reconnecting to an existing stream after a page refresh.

### 5.6 Context management

Confirmed:
- [ ] Preserve the full conversation history in PostgreSQL.
- [ ] Send only a bounded subset of recent conversation content to Gemini.
- [ ] Make the context limit configurable.
- [ ] Track token usage when the provider returns usage metadata.
- [ ] Detect when a conversation is approaching its configured context budget.
- [ ] Keep context management separate from permanent conversation storage.
- [ ] Defer automatic conversation summarization to a later iteration.

**Confirmed (v0.2) — token-budget approach:** Use a token budget rather than a
fixed number of messages. Reserve budget for the system prompt and the expected
assistant response, then include the most recent messages that fit.

- Default input budget: **20,000 tokens** for system prompt + history.
- Reserved for the response: **4,096 tokens**; safety margin: **512 tokens**.
- Hard cap of **60 messages** included regardless of budget.
- Selection walks backwards from the newest message, always includes the newest
  user message, and drops a leading assistant-only remainder so history starts
  with a user turn.
- Counts used for *selection* are local estimates and are never presented as
  provider truth. Provider-reported usage is what gets stored and displayed.
- If a conversation cannot fit even the system prompt plus newest message, the
  request fails with a non-retryable `context_too_large` error rather than
  silently truncating the user's message.

### 5.7 Token usage

- [ ] Display input and output token counts for each assistant response when Gemini provides usage metadata.
- [ ] If usage metadata is unavailable, display an unavailable/unknown state rather than presenting an invented exact count.
- [ ] Store usage metadata with the corresponding generation attempt when available.
- [ ] Do not add conversation-level usage dashboards or cost analytics in the MVP.

### 5.8 Failure handling and retry

The selected level is **Robust**.

- [ ] Apply request timeouts.
- [ ] Handle provider rate limits (for example, HTTP 429).
- [ ] Handle transient provider/server errors (for example, HTTP 5xx).
- [ ] Use bounded retries with exponential backoff for appropriate transient failures.
- [ ] Do not automatically retry non-retryable errors.
- [ ] Show clear user-facing error messages without exposing provider internals or secrets.
- [ ] Log useful diagnostic details while avoiding secrets and unnecessary conversation-content logging.
- [ ] Handle interrupted streams and client disconnects.
- [ ] Keep the user message if generation fails.
- [ ] Show a Retry action after a failed generation.
- [ ] Retry the existing user message; do not insert a duplicate user message.
- [ ] Track each generation attempt separately.
- [ ] Use attempt statuses such as `completed`, `failed`, and `interrupted`.
- [ ] Keep failed attempts out of the normal chat transcript; retain them for troubleshooting.
- [ ] Show interrupted attempts with any partial generated text and an interrupted status.
- [ ] Do not implement circuit breakers or fallback providers.

Retry policy details (maximum attempts, retryable status codes, and backoff limits) must be explicitly configured and tested. Avoid retrying a request when doing so could create duplicate persisted messages or duplicate generation attempts.

**Resolved (v0.2):**

- Maximum **2 automatic retries** after the initial attempt.
- Backoff: exponential from **1s** to an **8s** cap, with jitter.
- Retryable: connection errors, timeouts, HTTP 429, 500, 502, 503, 504, and
  provider stream error codes such as `gateway_timeout`.
- Not retryable: 400/401/403/404, validation failures, safety blocks, and
  `context_too_large`.
- Never retry once the first text token has been emitted for that attempt; the
  user gets the manual Retry action instead.
- A message submitted while a generation is active is rejected with **HTTP 409**
  and the active `attempt_id` in the error body.
- If the provider fails *after* text has streamed, the attempt becomes `failed`,
  the partial text stays visible with a failed marker, and Retry starts a new
  attempt. `interrupted` is reserved for user stop, refresh, and disconnect.

## 6. Architecture direction

### 6.1 Initial technology choices

| Area | Selected direction |
|---|---|
| Frontend | React + TypeScript, Vite, Tailwind CSS |
| Frontend data layer | TanStack Query |
| Markdown rendering | `react-markdown` + `remark-gfm` + `rehype-sanitize` + `rehype-highlight` |
| Backend | Python 3.12+ + FastAPI |
| Validation/contracts | Pydantic v2 |
| Database | PostgreSQL (Docker Compose for local development) |
| ORM | SQLAlchemy 2.x async + asyncpg (confirmed) |
| Migrations | Alembic (confirmed) |
| LLM | Gemini `gemini-3.5-flash-lite` (config-driven, see ADR-001) |
| Provider API | Gemini **Interactions API** (GA since June 2026) |
| Provider SDK | `google-genai` >= 2.3.0 |
| Provider state | Stateless from the provider's perspective (`store=false`) |
| Streaming | Server-Sent Events, POST response consumed via `fetch` stream |
| Python environment/package manager | `uv` |
| Tests | `pytest` (backend), Vitest + React Testing Library (frontend) |
| Lint/format | Ruff, ESLint + Prettier |
| Static typing | Pyright, TypeScript strict |
| HTTP client | HTTPX where an explicit async HTTP client is needed |
| CI | GitHub Actions (ruff, pyright, pytest with Postgres service, tsc, vitest) |
| Local environment | Postgres in Docker Compose; app processes run locally |

The Interactions API is Google's recommended interface for new projects and is
where new model and tool capabilities launch. Its event model
(`interaction.created` → `step.*` → `interaction.completed`) is richer than the
legacy `generateContent` stream, which is why the adapter maps a small, stable
subset of it and hides the rest.

**Rejected alternatives:** the legacy `generateContent` API (superseded, no new
capability launches), raw REST over HTTPX (more work, no learning benefit once
the SDK is isolated behind the adapter), and background execution with
`cancel(id)` (forces server-side state and job tracking far beyond MVP scope).

### 6.2 Provider boundary

- [ ] Define a small application-owned interface for chat generation and streaming.
- [ ] Implement Gemini behind that interface.
- [ ] Keep Gemini SDK types and provider-specific errors inside the Gemini adapter.
- [ ] Keep application and API layers dependent on application-owned request/response/event contracts.
- [ ] Do not implement a second provider in the MVP.
- [ ] Do not create a generic plugin system or over-generalized provider framework.
- [ ] **Resolved (v0.2):** Set `store=false` and never use `previous_interaction_id`. The application owns conversation state and context budgeting; the provider receives a bounded, self-contained request each turn.
- [ ] **Resolved (v0.2):** Map only these provider events into the application contract: `step.delta` with `delta.type == "text"` → text delta; `interaction.completed` → terminal usage; provider `error` events and HTTP failures → application error categories. `thought`, `thought_signature`, and `tool` steps are ignored in the MVP.

The abstraction should be just large enough to isolate provider-specific behavior and make the application testable with a fake provider. The interface is defined in ADR-003 and the implementation plan; it exposes an async iterator of application-owned events, not SDK objects.

### 6.3 Suggested logical components

The following is a proposed separation of responsibilities, not a requirement to create one class/module per bullet:

- **API layer:** FastAPI routes, request validation, SSE response lifecycle.
- **Application/service layer:** Conversation orchestration, context selection, generation-attempt lifecycle, retry coordination.
- **Domain/contracts:** Conversation/message/attempt concepts and provider-independent request/event types.
- **Persistence layer:** PostgreSQL repositories and transaction boundaries.
- **Provider adapter:** Gemini request mapping, streaming, usage metadata, cancellation, and provider error translation.
- **Frontend:** Sidebar, conversation view, message composer, stream handling, error/retry states, Markdown rendering.

Avoid premature microservices. This is one application with clear internal boundaries.

## 7. Data model

The schema below is confirmed. Migrations are owned by Alembic; the plan holds
the full column-level detail and invariants.

### Conversation — `conversations`
- `id` — UUIDv7 primary key
- `title` — text, max 80 code points, app-enforced
- `created_at`, `updated_at` — `updated_at` is bumped whenever a message is
  inserted, and is the primary sort key for the sidebar
- Index on `(updated_at DESC, id DESC)` for cursor pagination

### Message — `messages`
- `id` — UUIDv7 primary key
- `conversation_id` — FK, `ON DELETE CASCADE`
- `role` — `user` or `assistant`
- `content` — text (the canonical transcript text)
- `seq` — per-conversation integer sequence, `UNIQUE (conversation_id, seq)`,
  used as a stable display and reconstruction order
- `created_at`
- Index on `(conversation_id, seq)`

### GenerationAttempt — `generation_attempts`
- `id` — UUIDv7 primary key
- `conversation_id` — FK, `ON DELETE CASCADE`
- `user_message_id` — FK, `ON DELETE CASCADE`
- `assistant_message_id` — nullable FK, `ON DELETE SET NULL`
- `attempt_no` — integer, `UNIQUE (user_message_id, attempt_no)`
- `status` — `in_progress`, `completed`, `failed`, `interrupted`
- `provider`, `model` — provider identifier actually used
- `error_code`, `error_message` — nullable, sanitized, internal diagnostics only
- `input_tokens`, `output_tokens`, `thought_tokens`, `total_tokens` — nullable
  integers, populated only from provider usage metadata
- `usage_raw` — nullable JSONB, the provider usage object verbatim
- `started_at`, `completed_at`
- **Partial unique index on `(conversation_id) WHERE status = 'in_progress'`** —
  enforces "at most one active generation per conversation" in the database, not
  only in application code

Important behavior:
- A user message is saved before provider generation.
- A retry creates a new generation attempt associated with the same user message.
- A successful retry creates its own assistant message and links it to the new attempt.
- Failed attempts remain in attempt storage but do not appear as an assistant
  message unless text was already streamed before the failure, in which case the
  partial message stays visible with a failed marker.
- An interrupted attempt with partial text is visible in the conversation.
- Deleting a conversation permanently deletes its messages and attempts through
  `ON DELETE CASCADE`.

**Resolved (v0.2) — canonical content location:** assistant content lives on the
`messages` row. `generation_attempts` holds lifecycle, model, and usage metadata
plus a pointer to the message it produced. The transcript has exactly one
canonical representation, so rendering a conversation never joins attempt
content, and failed attempts naturally produce no visible message.

## 8. API surface

Routes and payloads are confirmed (v0.2). Full request/response examples and the
SSE framing live in the implementation plan.

- [ ] `GET /api/health` — liveness, no dependency checks.
- [ ] `GET /api/health/ready` — readiness, verifies database connectivity.
- [ ] `POST /api/chat` — body `{ conversation_id: uuid | null, content: string }`.
  Creates the conversation on first message, persists the user message, and
  returns `text/event-stream` for the assistant generation.
- [ ] `GET /api/conversations?cursor=&limit=20` — cursor-paginated list, newest
  `updated_at` first.
- [ ] `GET /api/conversations/{conversation_id}` — conversation plus its messages
  in `seq` order.
- [ ] `DELETE /api/conversations/{conversation_id}` — permanent delete, `204`.
- [ ] `POST /api/conversations/{conversation_id}/messages/{message_id}/retry` —
  returns `text/event-stream` for a new attempt on an existing user message.
- [ ] `POST /api/conversations/{conversation_id}/generations/{attempt_id}/stop` —
  idempotent cancellation, `202`, returns the attempt's current status.

API requirements:
- Validate input with Pydantic.
- Consistent error shape: `{"error": {"code": string, "message": string, "details": object | null}}`.
- Do not expose provider credentials or raw stack traces.
- Unknown conversation or message ids return `404` with `conversation_not_found`
  or `message_not_found`.
- A message submitted while a generation is active returns `409` with
  `generation_in_progress` and the active `attempt_id` in `details`.
- Retry is rejected with `409 generation_already_completed` when the latest
  attempt for that message completed successfully.
- Pagination is ordered by `(updated_at DESC, id DESC)` with an opaque cursor
  encoding both values. Invalid cursors return `400 invalid_cursor`.
- The stream is always terminated by exactly one `done` or `error` event; the
  frontend treats connection close without a terminal event as an interruption.
- Retries and client disconnects never create duplicate user messages: the user
  message is written once, before the provider call, and retry targets that row.

## 9. Security and privacy

- [ ] Store the Gemini API key only in backend environment configuration/secrets.
- [ ] Do not commit `.env` files or credentials.
- [ ] Provide an `.env.example` containing placeholders only.
- [ ] Do not expose secrets in frontend bundles, API responses, logs, or exception messages.
- [ ] Sanitize Markdown rendering and restrict unsafe content.
- [ ] Apply sensible request-size and message-size limits. **Resolved (v0.2):**
  user message content 1–16,000 characters after trimming; request body capped
  at 64 KiB by middleware; oversized input returns `413` or `422` per case.
- [ ] Send `store=false` to the provider so no interaction state is retained
  server-side beyond the request itself.
- [ ] Use synthetic/non-sensitive data with the Gemini free tier.
- [ ] Avoid logging full user prompts and assistant responses by default.
- [ ] Document that this is a local single-user learning project and has no authentication.
- [ ] Do not expose the local service publicly without revisiting authentication, authorization, rate limiting, and deployment security.

## 10. Reliability and observability

- [ ] Configure timeouts for provider calls.
- [ ] Use bounded retries only for eligible transient failures.
- [ ] Translate provider-specific errors into application-level error categories.
- [ ] Record generation status and timestamps.
- [ ] Record token usage when available.
- [ ] Log request/attempt identifiers and diagnostic error categories.
- [ ] Avoid logging secrets or full conversation content.
- [ ] Handle frontend disconnects and backend cancellation paths.
- [ ] Ensure a generation cannot remain indefinitely marked `in_progress`; define cleanup/reconciliation behavior for unexpected backend termination. **Resolved (v0.2):** at application startup, before accepting traffic, every attempt still `in_progress` is marked `interrupted` with `error_code = process_restart` and `completed_at = now()`. Because partial text is only written at terminal state, a crashed attempt keeps whatever text was already persisted for the user message and shows no assistant content; the user can retry. The partial unique index guarantees the cleanup leaves no conversation permanently blocked.

## 11. Testing strategy

### Unit tests
- [ ] Context-window selection and budget handling.
- [ ] Conversation title generation and 80-character save-time limit.
- [ ] Provider error translation.
- [ ] Retry eligibility and bounded backoff policy.
- [ ] Generation-attempt status transitions.
- [ ] Conversation/message ordering.
- [ ] Usage metadata handling when present or absent.

### Integration tests
- [ ] Persistence of conversations and messages.
- [ ] User message remains stored when provider generation fails.
- [ ] Retry reuses the same user message and creates a distinct attempt.
- [ ] Successful streaming persists the completed assistant response.
- [ ] Stop/disconnect persists partial text as interrupted.
- [ ] Conversation deletion removes related records.
- [ ] Pagination returns stable results when new conversations are created.

### API/stream tests
- [ ] SSE emits text incrementally.
- [ ] SSE emits a terminal completion event.
- [ ] SSE reports provider errors in a client-safe format.
- [ ] Client disconnect triggers cancellation handling.
- [ ] Stop action triggers cancellation handling.
- [ ] No second message is accepted while a generation is active.

### Frontend tests
- [ ] Create/open/delete conversation flows.
- [ ] Sidebar pagination and ordering.
- [ ] Streaming message rendering.
- [ ] Composer disabled while generating.
- [ ] Stop and retry interactions.
- [ ] Interrupted response display.
- [ ] Markdown sanitization and code-block copy.
- [ ] Token usage display and unavailable state.

### End-to-end/manual checks
- [ ] Fresh Docker Compose startup works from documented instructions.
- [ ] User can send a message and see a streamed Gemini response.
- [ ] Refresh during generation produces the agreed interrupted behavior.
- [ ] A failed generation can be retried without duplicating the user message.
- [ ] Conversations survive application restarts.
- [ ] Deleting a conversation removes it from the sidebar and database.

Tests should use a fake provider for deterministic behavior. Live Gemini tests should be opt-in/manual or isolated, so the normal test suite does not depend on network access, quotas, or paid inference.

**Resolved (v0.2):** backend tests use `pytest` + `pytest-asyncio` against a
disposable PostgreSQL database; frontend tests use Vitest + React Testing
Library with a fetch mock that replays recorded SSE frames. The fake provider is
a first-class adapter implementation, so application tests never import Gemini
types.

## 12. Acceptance criteria

The MVP is considered complete when:

- [ ] A developer can start the frontend, backend, and PostgreSQL through Docker Compose using documented steps.
- [ ] The user can create a new chat by submitting the first message.
- [ ] The user receives a streamed Gemini response.
- [ ] Conversations and messages persist across restarts.
- [ ] The sidebar lists conversations newest/recently updated first and supports pagination.
- [ ] Conversation titles are derived from the first message, limited to 80 characters when saved, and visually truncated as needed.
- [ ] The user can open, continue, and permanently delete conversations.
- [ ] Assistant Markdown and code blocks render safely, with syntax highlighting and per-block copy actions.
- [ ] The user can stop generation and see any partial response marked interrupted.
- [ ] Refreshing/disconnecting during generation follows the same cancellation/interruption behavior.
- [ ] The user cannot submit another message while a response is active.
- [ ] Provider failures are handled robustly and the user can retry the original message.
- [ ] Generation attempts and statuses are persisted separately from the normal chat display.
- [ ] Per-response token usage is displayed when returned by Gemini.
- [ ] The full conversation is retained in PostgreSQL while only a bounded context is sent to Gemini.
- [ ] Automated tests cover core persistence, orchestration, failure, retry, and streaming behavior.
- [ ] No authentication, RAG, agents, tools, file uploads, search, or cloud deployment have crept into the MVP.

## 13. Implementation milestones

Keep each milestone small, reviewable, and demonstrable. Do not scaffold the entire application before validating the design.

> **v0.2:** The milestones below remain the authoritative sequence. Task-level
> breakdown, exit criteria, and the validation command for each milestone live in
> [`../plans/implementation-plan.md`](../plans/implementation-plan.md).

### Milestone 0 — Confirm design
- [ ] Resolve the open decisions in this document.
- [ ] Create initial architecture diagram.
- [ ] Define API/SSE event contracts.
- [ ] Define data model and transaction boundaries.
- [ ] Record meaningful decisions in ADRs.

### Milestone 1 — Project foundation
- [ ] Create repository structure.
- [ ] Set up Python with `uv`.
- [ ] Set up FastAPI and `/health`.
- [ ] Set up Ruff, Pyright, and pytest.
- [ ] Add Docker Compose and PostgreSQL.
- [ ] Add React + TypeScript application.
- [ ] Document local setup.

### Milestone 2 — Persistence and conversations
- [ ] Add SQLAlchemy/Alembic if confirmed.
- [ ] Implement conversation/message/attempt persistence.
- [ ] Implement create-on-first-message behavior.
- [ ] Implement list/open/delete and pagination.
- [ ] Add persistence integration tests.

### Milestone 3 — Basic Gemini integration
- [ ] Define provider-independent contracts.
- [ ] Implement Gemini adapter.
- [ ] Add backend configuration and secret handling.
- [ ] Add system prompt configuration.
- [ ] Implement non-streaming provider test path if useful for validating the adapter.
- [ ] Add fake-provider tests.

### Milestone 4 — Streaming chat
- [ ] Define SSE event contract.
- [ ] Implement streamed generation.
- [ ] Persist user message before generation.
- [ ] Persist assistant output and attempt status.
- [ ] Implement frontend stream handling.
- [ ] Add cancellation and disconnect behavior.

### Milestone 5 — Context and resilience
- [ ] Implement configurable context budgeting.
- [ ] Reserve room for system prompt and assistant output.
- [ ] Track provider usage metadata.
- [ ] Implement robust error translation and bounded retries.
- [ ] Implement retry action using the existing user message.
- [ ] Add token usage display.
- [ ] Test interrupted and failed attempts.

### Milestone 6 — UI polish and acceptance
- [ ] Complete ChatGPT-like sidebar/chat layout.
- [ ] Add safe Markdown and syntax highlighting.
- [ ] Add code-block copy.
- [ ] Add title truncation and pagination UX.
- [ ] Run acceptance checklist.
- [ ] Update README and architecture documentation.

## 14. Collaboration and implementation rules

Use the AI coding assistant as a pair programmer, not as an autonomous project owner.

Before any significant change—especially architecture, dependencies, persistence, API contracts, security, deployment, or broad scaffolding—the assistant must:

1. Explain the problem and why a decision is needed.
2. Present viable options and meaningful trade-offs.
3. Ask focused questions and let the user make the decision.
4. Make a recommendation, clearly labeled as a recommendation.
5. Wait for the user's decision before implementing.
6. Record the agreed decision in this spec or an ADR.
7. Implement in small, reviewable steps.
8. Explain what changed, why, how to test it, and what trade-offs remain.

Do not:
- Silently introduce unapproved features or dependencies.
- Generate large amounts of code before the relevant design decisions are agreed.
- hide complexity behind abstractions the user has not had a chance to understand.
- treat generated code as correct without reviewing and testing it.
- make production, security, or cost claims without verifying them.

For small reversible implementation details already covered by an agreed requirement, the assistant may choose a sensible default and explain it in the change summary.

## 15. Decision ledger

### Resolved (v0.2, 2026-10-28)

| # | Decision | Outcome |
|---|---|---|
| 1 | Context-window policy | Token budget: 20,000 input tokens, 4,096 reserved for output, 512 margin, 60-message hard cap, backwards selection |
| 2 | Gemini model and API support | `gemini-3.5-flash-lite` via the Interactions API (`google-genai` >= 2.3.0); streaming, usage metadata, and mid-stream error events verified in current docs |
| 3 | Persistence implementation | SQLAlchemy 2.x async + asyncpg + Alembic |
| 4 | SSE event names and payloads | `meta`, `delta`, `usage`, `done`, `error`; exactly one terminal event per stream |
| 5 | Cancellation mechanism and active-generation tracking | In-process `attempt_id → asyncio.Task` registry; stop endpoint cancels the task; disconnect detection cancels too; DB partial unique index backs the invariant |
| 6 | Partial assistant content persistence | In-memory buffer, single write at terminal state; startup reconciliation marks stranded `in_progress` attempts `interrupted` with `process_restart` |
| 7 | Failed attempt in the UI | No placeholder for pre-token failures (error + Retry attached to the user message). Post-token failures keep partial text visible with a failed marker |
| 8 | Retry limits and backoff | 2 automatic retries, 1s exponential base, 8s cap, jitter, pre-first-token only |
| 9 | Message and request size limits | 1–16,000 characters per message; 64 KiB request body cap |
| 10 | Pagination cursor and page size | Opaque cursor over `(updated_at DESC, id DESC)`, default/max 20 per page, UUIDv7 ids |
| 11 | Title length and truncation | 80 Unicode code points at save time, whitespace-normalized, word-boundary-aware cut, CSS ellipsis in the sidebar |
| 12 | Initial system prompt | Minimal, format-aware general assistant; version-controlled file, no persona, no injected knowledge |
| 13 | Frontend styling and components | Vite + React + TypeScript, Tailwind CSS, `react-markdown` + `remark-gfm` + `rehype-sanitize` + `rehype-highlight`, TanStack Query |
| 14 | Docker Compose layout and hot reload | PostgreSQL only in Compose; backend (`uv`) and frontend (`vite`) run on the host; a full-stack Compose profile is added for acceptance verification |
| 15 | Startup reconciliation for stranded attempts | Mark all `in_progress` attempts `interrupted` with `process_restart` during application startup |
| 16 | Provider-side conversation state | `store=false`, stateless from the provider's perspective; the app owns all context |
| 17 | Stream transport | `POST` returning `text/event-stream`, consumed with `fetch` + `ReadableStream` |
| 18 | Concurrent message handling | `409 generation_in_progress` including the active `attempt_id` |
| 19 | Error classification with partial output | Post-token provider failure → `failed` with partial text kept visible; `interrupted` is reserved for stop/refresh/disconnect |
| 20 | Identity scheme | UUIDv7 primary keys for conversations, messages, and attempts |

### Deferred to later iterations (explicitly out of MVP scope)

- **Model registry / model picker.** See the model-churn risk in
  [`../plans/implementation-plan.md`](../plans/implementation-plan.md). The model
  id is configuration, not code, so swapping it is a one-line change, but there
  is no UI or fallback yet.
- Automatic conversation summarization.
- Conversation search, export, archiving, regeneration, message editing.
- Authentication, multi-user isolation, rate limiting.
- Cloud deployment, IaC, CI/CD beyond GitHub Actions checks.
- Second provider, fallback provider, circuit breakers.
- Tool calling, RAG, multimodal input.

---

## Decision log

| Topic | Decision |
|---|---|
| User model | Single user |
| Authentication | None in MVP |
| UI | ChatGPT-like sidebar and chat view |
| History | Persistent PostgreSQL storage |
| Conversation creation | On first submitted message |
| Context | Bounded token budget (20k input, 4k reserved output), app-owned |
| Capabilities | General-purpose assistant only |
| Streaming | Yes, from the beginning; SSE |
| Model controls | One backend-configured Gemini model |
| Error handling | Robust |
| Editing/regeneration | Deferred |
| Titles | Deterministic from first user message |
| Title length | Revised to max 80 characters when saved, plus UI truncation |
| Delete | Permanent conversation deletion |
| Response rendering | Markdown, syntax highlighting, code-block copy |
| System prompt | Version-controlled backend configuration file |
| Deployment | Local Docker Compose |
| Provider integration | Small provider boundary; Gemini only |
| Stop generation | Yes; preserve partial output as interrupted |
| Concurrent user messages | Not allowed while generating |
| Conversation save | On first user message |
| Provider failure | Preserve user message |
| Retry | Yes; reuse original user message |
| Browser refresh during generation | Cancel and preserve partial output as interrupted |
| Generation attempts | Track separately; failures hidden from normal transcript, interrupted partials visible |
| Token usage | Show per response when available |
| Full conversation copy/export | Not in MVP |
| Conversation search | Not in MVP |
| Sidebar | Cursor-paginated, newest/recently updated first |
| Identity | UUIDv7 primary keys for all three entities |
| Ordering key | `(updated_at DESC, id DESC)`; `updated_at` bumps on message insert |
| Provider API | Gemini Interactions API (`google-genai` >= 2.3.0), not `generateContent` |
| Provider state | Stateless requests (`store=false`); app owns conversation history |
| Model | `gemini-3.5-flash-lite`; model churn is a tracked risk, model picker deferred |
| Persistence stack | SQLAlchemy 2.x async + asyncpg + Alembic |
| Assistant content | Canonical on `messages.content`; attempts hold lifecycle/usage metadata only |
| Active generation invariant | One `in_progress` attempt per conversation, enforced by partial unique index |
| Stop mechanism | Cancel asyncio task + close stream; provider may finish server-side (accepted) |
| Stream consumption | `POST` + `text/event-stream` parsed via `fetch`, not `EventSource` |
| Stream events | `meta`, `delta`, `usage`, `done`, `error`; one terminal event |
| Retry policy | 2 automatic retries, 1s→8s jittered backoff, pre-first-token only |
| Concurrent message rejection | `409 generation_in_progress` with active `attempt_id` |
| Post-token provider failure | `failed`, partial text kept visible, Retry creates a new attempt |
| Context budget | 20,000 input tokens, 4,096 output reserve, 512 margin, 60-message cap |
| Message size | 1–16,000 characters; 64 KiB request body cap |
| Title rule | 80 code points, whitespace-normalized, word-boundary-aware cut |
| Crash recovery | Startup reconciliation marks stranded attempts `interrupted` (`process_restart`) |
| Frontend stack | Vite + React + TS, Tailwind, react-markdown + rehype-sanitize + rehype-highlight, TanStack Query |
| Test stacks | pytest + pytest-asyncio; Vitest + React Testing Library |
| CI | GitHub Actions from Milestone 1 |
| Local dev layout | Postgres in Compose; backend and frontend on the host |
