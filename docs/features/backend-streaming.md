---
id: LUCID-STREAM-001
title: Provider streaming and cancellation
paths:
  - backend/src/lucid/application/chat/streaming.py
  - backend/src/lucid/application/chat/events.py
  - backend/src/lucid/domain/provider.py
  - backend/src/lucid/providers/streams.py
links:
  - docs/decisions/ADR-003-provider-boundary-streaming-cancellation.md
verificationMethod: automated-test
---

# Provider streaming and cancellation

## Overview

Streams provider text and completion events and closes the provider stream when
the request ends or is cancelled.

### [LUCID-STREAM-RULE-001] Closing a provider stream is timeout-bounded
Closing a provider stream waits for at most the configured timeout.

### [LUCID-STREAM-RULE-002] Close errors are swallowed
An error while closing an already-finished stream does not fail the response.

### [LUCID-STREAM-RULE-003] A stream without close is ignored
A provider stream that does not expose a close method is left alone.

### [LUCID-STREAM-RULE-004] Text and completion keep their order
Text deltas are emitted before the completion event, and the completion carries
the usage when the provider supplies it.
