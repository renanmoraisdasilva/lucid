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
