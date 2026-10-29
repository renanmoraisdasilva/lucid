# Gemini adapter notes

Verified against `google-genai` **2.34.0** on **2026-10-29** with
`gemini-3.5-flash-lite`. These are the facts the adapter depends on; re-check them
before changing the SDK version or the model.

## Client and call shape

```python
client = genai.Client(
    api_key=...,
    http_options=types.HttpOptions(timeout=60_000),  # milliseconds
)

stream = await client.aio.interactions.create(
    model="gemini-3.5-flash-lite",
    input=[...],                    # see "Multi-turn input" below
    system_instruction="...",
    generation_config={"max_output_tokens": 2048},
    stream=True,
    store=False,
    automatic_continuation=False,
)
```

- `create` is a **coroutine** that resolves to `AsyncStream`, not an async
  generator. `async for` works on the resolved value.
- `AsyncStream.close()` is a **coroutine**; calling it synchronously emits a
  "coroutine was never awaited" warning.
- The published signature lists `request` / `body`, but keyword arguments
  (`model=`, `input=`, ...) are accepted and build the body. Pyright sees the
  `Interaction` return type, not `AsyncStream`, so the adapter casts once.
- `timeout` as a **per-request** argument did not behave as expected (a 5s value
  produced an immediate `APITimeoutError`). Use the client-level
  `http_options.timeout` in milliseconds instead.

## Multi-turn input (stateless)

`input` accepts `Content | Content[] | Step[] | string`. History is an array of
**steps**, not `role`/`content` pairs:

```python
[
    {"type": "user_input",   "content": [{"type": "text", "text": "My name is Renan."}]},
    {"type": "model_output", "content": [{"type": "text", "text": "Hello Renan."}]},
    {"type": "user_input",   "content": [{"type": "text", "text": "What is my name?"}]},
]
```

Confirmed working: the model answered from history with `store=False`. Passing
`{"role": ..., "content": ...}` fails with a Pydantic union error (the SDK tries
`CreateAgentInteraction`, which requires `agent`).

## Streaming events

Observed order: `interaction.created` → `interaction.status_update` →
`step.start` → `step.delta`* → `step.stop` → `interaction.completed`.

- The **first** `step.delta` is frequently `thought_signature`, not text. Filter
  on `delta.type == "text"`; ignore `thought_summary`, tool deltas, and any
  `json` deltas.
- `interaction.completed` carries `interaction.status`
  (`completed`, `failed`, `cancelled`, `incomplete`, `requires_action`,
  `requires_continuation`) and `interaction.usage`.
- `error` events carry `{"code": "...", "message": "..."}` mid-stream; codes seen
  in docs: `gateway_timeout`, `not_found`, `unavailable`, `overloaded`,
  `resource_exhausted`, `invalid_argument`.

## Usage metadata

`usage.model_dump()` returns:

```json
{
  "initial_input_tokens": 9,
  "input_tokens_by_modality": [{"modality": "text", "tokens": 11}],
  "total_cached_tokens": 0,
  "total_input_tokens": 11,
  "total_output_tokens": 1,
  "total_thought_tokens": 0,
  "total_tokens": 12,
  "total_tool_use_tokens": 0
}
```

Store `total_*` fields; keep the raw object for diagnostics. Thought tokens are
billed as output but are not rendered.

## Errors

| Situation | Exception | `status_code` |
|---|---|---|
| Model does not exist | `NotFoundError` | 404 |
| Invalid API key | `BadRequestError` | 400 |
| Rate limit | `ClientError` | 429 |
| Server fault | `ServerError` | 500–599 |
| Request timeout | `APITimeoutError` | — |
| Connection failure | `APIConnectionError` | — |

`APITimeoutError` / `APIConnectionError` live in
`google.genai._gaos.lib.compat_errors` — an **internal** module. The adapter
therefore classifies by status code and by class name instead of importing them.
Domain error messages are fixed strings; provider text is kept in
`ProviderError.detail` for logs only.

## Token counting

`client.aio.models.count_tokens` exists, but it accepts `generateContent` content
shapes (`Content`, `Part`, ...). `client.aio.interactions` exposes no counting
method, and converting our steps back into `contents` would cost a network round
trip per turn for an approximate number.

**Decision:** selection uses the local heuristic in
`application/context.py` (`ceil(characters / 4)` plus 4 tokens per message). The
provider's reported usage is the only exact count and is the only number stored
or displayed. The system prompt, reserved output, and a safety margin are
subtracted before selection.

## Cancellation (verified 2026-10-29)

- **Client disconnect** during a real stream: Starlette cancels the response
  task, the service finalizes the attempt as `interrupted` with the partial text,
  and the SDK stream closes without warnings. Verified against
  `gemini-3.5-flash-lite` by aborting a stream after 4 seconds; the stored
  conversation had the user message plus a 43-character interrupted assistant
  message and no active attempt.
- **Stop** is cooperative: the streaming loop checks the registry's stop event
  between deltas so it can still emit `done {status: "interrupted"}`. A 1.5-second
  grace timer cancels the task if the provider stalls.
- `AsyncStream.close()` is a coroutine and is awaited in the adapter's `finally`.

## Not yet verified

- Behaviour when `max_output_tokens` is hit (`incomplete` status) — mapped to
  `finish_reason = "length"` on the completion path, not exercised end to end.
- Free-tier rate limits for this model; they are visible only in AI Studio.
- The stop grace timer firing against a stalled provider (only the cooperative
  path has been exercised so far).
