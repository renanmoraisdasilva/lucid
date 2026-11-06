---
id: UI-SSE-001
title: Server-sent event parsing
paths:
  - frontend/src/api/sse.ts
links:
  - docs/decisions/ADR-003-provider-boundary-streaming-cancellation.md
verificationMethod: automated-test
---

# Server-sent event parsing

## Overview

Parses named SSE frames across chunk boundaries.

### [UI-SSE-RULE-001] Named events are emitted in order
A frame with a named event reaches the caller in the same order it arrived.

### [UI-SSE-RULE-002] A frame split across chunks is reassembled
A frame may arrive in pieces; the parser waits for the blank line before
emitting it.

### [UI-SSE-RULE-003] CRLF and heartbeat lines are handled
CRLF line endings are accepted, and comment heartbeat lines are ignored.

### [UI-SSE-RULE-004] A trailing frame is emitted without a final blank line
When the stream ends with a complete frame but no final blank line, the frame is
still emitted.
