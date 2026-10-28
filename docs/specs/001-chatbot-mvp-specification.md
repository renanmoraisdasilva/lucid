# Chatbot MVP — Product & Technical Specification

**Status:** Draft based on discovery interview  
**Version:** 0.1  
**Last updated:** 2026-10-28

> This specification records the decisions made during the interview. Items marked **Proposed** or **Open** are not yet confirmed requirements. Checkboxes are intended to track implementation and acceptance.

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
- [ ] **Revised decision:** Also apply a maximum title length when saving. The proposed limit is **80 characters**, then truncate visually in the UI if the available sidebar width requires it. Confirm exact truncation behavior during implementation.

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
- [ ] Define explicit stream event types for text deltas, completion, and errors (exact event contract to be finalized in the API design).
- [ ] Persist the user message before starting provider generation.
- [ ] Persist assistant output as it is generated or otherwise ensure received partial output can be recovered and saved when the stream ends.
- [ ] Allow the user to stop generation.
- [ ] On stop, attempt to cancel the provider request and preserve received text as an `interrupted` assistant generation attempt.
- [ ] If the browser refreshes or disconnects during generation, cancel the generation and preserve received text as interrupted.
- [ ] Account for the possibility that provider-side cancellation is not immediate or cannot be guaranteed.
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

**Proposed approach — needs confirmation:** Use a token budget rather than a fixed number of messages. Reserve budget for the system prompt and expected assistant response, then include the most recent messages that fit. The exact token-counting strategy must account for the fact that provider tokenization may differ from local estimates. Do not silently treat an estimate as exact provider usage.

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

## 6. Architecture direction

### 6.1 Initial technology choices

| Area | Selected direction |
|---|---|
| Frontend | React + TypeScript |
| Backend | Python + FastAPI |
| Validation/contracts | Pydantic |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2.x (proposed implementation choice) |
| Migrations | Alembic (proposed implementation choice) |
| LLM | Gemini |
| Provider SDK | Official Gemini Python SDK/API; exact package/API to verify at implementation time |
| Streaming | Server-Sent Events |
| Python environment/package manager | `uv` |
| Tests | `pytest` |
| Lint/format | Ruff |
| Static typing | Pyright |
| HTTP client | HTTPX where an explicit async HTTP client is needed |
| Local environment | Docker Compose |

SQLAlchemy, Alembic, and the exact Gemini SDK package are implementation recommendations, not yet separately confirmed interview decisions. Verify current SDK support and streaming behavior before choosing the concrete integration.

### 6.2 Provider boundary

- [ ] Define a small application-owned interface for chat generation and streaming.
- [ ] Implement Gemini behind that interface.
- [ ] Keep Gemini SDK types and provider-specific errors inside the Gemini adapter.
- [ ] Keep application and API layers dependent on application-owned request/response/event contracts.
- [ ] Do not implement a second provider in the MVP.
- [ ] Do not create a generic plugin system or over-generalized provider framework.

The abstraction should be just large enough to isolate provider-specific behavior and make the application testable with a fake provider.

### 6.3 Suggested logical components

The following is a proposed separation of responsibilities, not a requirement to create one class/module per bullet:

- **API layer:** FastAPI routes, request validation, SSE response lifecycle.
- **Application/service layer:** Conversation orchestration, context selection, generation-attempt lifecycle, retry coordination.
- **Domain/contracts:** Conversation/message/attempt concepts and provider-independent request/event types.
- **Persistence layer:** PostgreSQL repositories and transaction boundaries.
- **Provider adapter:** Gemini request mapping, streaming, usage metadata, cancellation, and provider error translation.
- **Frontend:** Sidebar, conversation view, message composer, stream handling, error/retry states, Markdown rendering.

Avoid premature microservices. This is one application with clear internal boundaries.

## 7. Data model — initial proposal

The exact schema is to be designed and recorded before implementation. The following entities are expected:

### Conversation
- `id`
- `title`
- `created_at`
- `updated_at`

### Message
- `id`
- `conversation_id`
- `role` (at minimum `user` or `assistant`)
- `content`
- `created_at`
- Ordering information sufficient to reconstruct the conversation reliably.

### GenerationAttempt
- `id`
- `conversation_id`
- `user_message_id`
- `assistant_message_id` (nullable if no assistant content was created)
- `status` (`in_progress`, `completed`, `failed`, `interrupted`)
- Provider/model identifier used for the attempt
- Usage metadata (nullable)
- Error category/code safe for internal diagnostics (nullable)
- Started/completed timestamps
- Optional diagnostic metadata that does not contain secrets

Important behavior:
- A user message is saved before provider generation.
- A retry creates a new generation attempt associated with the same user message.
- A successful retry creates/associates its own assistant response.
- Failed attempts remain in attempt storage but do not appear as normal assistant chat messages.
- An interrupted attempt with partial text is visible in the conversation.
- Deleting a conversation permanently deletes its messages and attempts (transactionally or via well-defined cascading behavior).

**Open design point:** Decide whether assistant content is stored directly on the generation-attempt record or in the `Message` table with a link to its attempt. Prefer one canonical representation; avoid duplicating the same content in two tables.

## 8. API surface — initial proposal

Exact routes and payloads are to be finalized in an API contract before implementation. Likely operations:

- [ ] Health check endpoint.
- [ ] Create a conversation implicitly on first submitted message.
- [ ] List conversations using cursor-based pagination.
- [ ] Retrieve a conversation and its messages.
- [ ] Delete a conversation.
- [ ] Submit a user message and receive an SSE stream for the assistant generation.
- [ ] Retry generation for an existing user message.
- [ ] Stop/cancel the active generation (exact mechanism to be designed alongside SSE).

API requirements:
- Validate input with Pydantic.
- Use consistent error response shapes.
- Do not expose provider credentials or raw stack traces.
- Define behavior for unknown conversation IDs and invalid message references.
- Define ordering and pagination semantics.
- Define how the frontend distinguishes a completed, failed, or interrupted stream.
- Ensure retries and client disconnects do not create duplicate user messages.

## 9. Security and privacy

- [ ] Store the Gemini API key only in backend environment configuration/secrets.
- [ ] Do not commit `.env` files or credentials.
- [ ] Provide an `.env.example` containing placeholders only.
- [ ] Do not expose secrets in frontend bundles, API responses, logs, or exception messages.
- [ ] Sanitize Markdown rendering and restrict unsafe content.
- [ ] Apply sensible request-size and message-size limits (exact limits to be decided).
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
- [ ] Ensure a generation cannot remain indefinitely marked `in_progress`; define cleanup/reconciliation behavior for unexpected backend termination.

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

## 15. Open decisions to resolve before implementation

- [ ] Confirm context-window policy: fixed message count, or token budget with reserved space for system prompt and output. **Recommended: token budget with safety margin.**
- [ ] Confirm exact Gemini model and current SDK/API support for streaming, cancellation, and usage metadata.
- [ ] Confirm SQLAlchemy 2.x and Alembic as the persistence implementation.
- [ ] Decide exact SSE event names and payload schema.
- [ ] Decide exact cancellation mechanism and how active generations are tracked.
- [ ] Decide how to persist partial assistant content safely during streaming.
- [ ] Decide whether a failed attempt has a visible placeholder in the UI or only an error/retry state attached to the user message.
- [ ] Decide exact retry limits, retryable error categories, and backoff values.
- [ ] Decide message-size and request-size limits.
- [ ] Decide cursor format and page size for conversation pagination.
- [ ] Decide whether the 80-character title limit counts Unicode characters/code points and how truncation handles word boundaries.
- [ ] Decide the system prompt's initial content.
- [ ] Decide frontend styling/component-library approach.
- [ ] Decide local Docker Compose service layout and development hot-reload approach.
- [ ] Define cleanup/reconciliation for attempts left `in_progress` after an unexpected backend crash.

---

## Decision log

| Topic | Decision |
|---|---|
| User model | Single user |
| Authentication | None in MVP |
| UI | ChatGPT-like sidebar and chat view |
| History | Persistent PostgreSQL storage |
| Conversation creation | On first submitted message |
| Context | Recent messages, configurable limit; token-budget approach proposed |
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
