---
id: LUCID-STREAM-001
title: Provider streaming and cancellation
paths:
  - backend/src/lucid/application/chat/streaming.py
  - backend/src/lucid/application/chat/events.py
  - backend/src/lucid/domain/provider.py
  - backend/src/lucid/providers/streams.py
verificationMethod: automated-test
---

# Provider streaming and cancellation

## Overview

Streams provider text and completion events, records usage, and closes the
provider stream promptly when the client stops or the request is cancelled.
