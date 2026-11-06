---
id: UI-SSE-001
title: Server-sent event parsing
paths:
  - frontend/src/api/sse.ts
verificationMethod: automated-test
---

# Server-sent event parsing

## Overview

Parses named SSE frames across chunk boundaries, including CRLF lines, comment
heartbeats, and a trailing frame without a final blank line.

### [UI-SSE-FRAME-001] Named events are emitted in order
A frame with a named event reaches the caller in the same order it arrived.

### [UI-SSE-FRAME-002] A frame split across chunks is reassembled
A frame may arrive in pieces; the parser waits for the blank line before
emitting it.
