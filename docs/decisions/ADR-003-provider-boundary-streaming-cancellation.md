# ADR-003 — Provider boundary, streaming transport, and cancellation

- **Status:** Accepted
- **Date:** 2026-10-28
- **Deciders:** Renan Silva (with AI assistant)
- **Related:** ADR-001, ADR-005

## Context

Three coupled decisions: what the application-owned provider interface looks
like, how the browser receives tokens, and how generation is cancelled.

Constraints discovered while verifying the provider API:

- `EventSource` only issues `GET` requests and cannot send a body, but sending a
  message requires a `POST` with JSON.
- `cancel(id)` exists only for background interactions, which we do not use.
- A generation must be cancellable from a Stop button and from a client
  disconnect, and the received text must survive as `interrupted`.

## Decision

### Provider interface

A narrow protocol in the domain layer, with no SDK types in its signature:

```python
class ChatProvider(Protocol):
    name: str
    def stream(self, request: GenerationRequest) -> AsyncIterator[ProviderEvent]: ...

@dataclass(frozen=True)
class GenerationRequest:
    model: str
    system_prompt: str
    messages: Sequence[ProviderMessage]   # role + content, oldest first
    max_output_tokens: int
    request_id: str                        # correlation id for logs

@dataclass(frozen=True)
class TextDelta:      text: str
@dataclass(frozen=True)
class Usage:          input_tokens: int | None
                      output_tokens: int | None
                      thought_tokens: int | None
                      total_tokens: int | None
                      raw: Mapping[str, object] | None
@dataclass(frozen=True)
class StreamCompleted: usage: Usage | None

ProviderEvent = TextDelta | StreamCompleted
```

The adapter translates SDK exceptions into a domain error hierarchy
(`ProviderRateLimited`, `ProviderTimeout`, `ProviderUnavailable`,
`ProviderInvalidRequest`, `ProviderSafetyBlocked`, `ProviderStreamError`,
`ContextTooLarge`), each carrying a stable `code` and a `retryable` flag. No SDK
exception may escape the adapter.

### Stream transport

`POST /api/chat` and the retry endpoint return `text/event-stream`. The browser
consumes the body with `fetch` + `ReadableStream` + `TextDecoder` and a small
frame parser. Response headers include `Cache-Control: no-cache`,
`X-Accel-Buffering: no`, and `Connection: keep-alive`.

Event sequence: `meta` → zero or more `delta`/`usage` → exactly one terminal
`done` or `error`, then close.

### Cancellation and active-generation tracking

An in-process registry maps `attempt_id → asyncio.Task`:

- **Stop** — `POST /api/conversations/{cid}/generations/{aid}/stop` cancels the
  task, which closes the provider stream. Idempotent: an already-terminal
  attempt returns its current status.
- **Disconnect/refresh** — the streaming generator sees `CancelledError`
  (Starlette cancels the response task when the client goes away) and finalizes
  the attempt as `interrupted`.
- **Finalization under cancellation** must be shielded
  (`asyncio.shield` or a detached task) so the database write is not itself
  cancelled mid-flight. This is the subtlest bug class in the streaming path and
  has a dedicated test.
- Terminal persistence happens in **one transaction** before the terminal SSE
  event is emitted, so a client that reacts to `done` can re-fetch and see the
  committed message.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| `EventSource` after a `POST` that returns 202 | Native client, but two requests, a subscribe/POST race, and a second error path for the POST. The spec forbids reconnect, so `EventSource`'s main advantage is unused. |
| WebSockets | Contradicts the spec's SSE decision and adds connection lifecycle management for no MVP benefit. |
| Redis/DB-backed cancellation token polled by the loop | Survives restarts and multiple instances; adds latency, writes, and a second state machine. Deferred until the app is multi-process. |
| Drain the stream after stop and discard output | Burns quota on unseen text; also delays the terminal state. |
| Provider abstraction with capability flags, adapters registry, config-driven provider selection framework | Over-generalization explicitly forbidden by the spec. One protocol, two implementations (Gemini, fake). |

## Consequences

**Positive**

- Tests can run the entire application against the fake provider with no
  network, no quota, and deterministic timing.
- Exactly one streaming path serves first messages and retries.
- The frontend never depends on provider event names.

**Negative / accepted costs**

- The registry is process-local: multiple backend workers or instances would
  break Stop and the active-generation invariant's in-memory half. The MVP runs
  a single process; the database partial unique index still protects the data.
- After a stop, the provider may continue generating server-side. Accepted and
  documented; `max_output_tokens` is capped to limit waste.
- Buffering text in memory means a hard process crash loses the partial
  assistant text. Accepted; the attempt is reconciled to `interrupted` with
  `error_code = process_restart` on next startup (ADR-005).

## Follow-ups

- If the project ever runs more than one worker, replace the registry with the
  DB-backed cancellation design and record a new ADR.
