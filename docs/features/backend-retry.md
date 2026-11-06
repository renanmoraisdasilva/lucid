---
id: LUCID-RETRY-001
title: Retry, backoff, and provider cool-down
paths:
  - backend/src/lucid/application/retry.py
  - backend/src/lucid/application/cooldown.py
  - backend/src/lucid/application/chat/retries.py
links:
  - docs/decisions/ADR-005-failure-semantics-and-retry.md
verificationMethod: automated-test
---

# Retry, backoff, and provider cool-down

## Overview

Decides whether a failed turn may be retried and how long to wait.

### [LUCID-RETRY-RULE-001] Transient failures are retried before output
A transient provider failure before the first token is retryable.

### [LUCID-RETRY-RULE-002] Failures after output are not retried
Once text has reached the client, the turn is not retried, because a second
answer would duplicate visible output.

### [LUCID-RETRY-RULE-003] Permanent failures are never retried
Invalid requests, authentication failures, and other permanent errors stop
immediately.

### [LUCID-RETRY-RULE-004] Backoff doubles and caps
The retry delay doubles per attempt and stops growing at the configured cap.

### [LUCID-RETRY-RULE-005] Provider cool-down never shortens
A new provider cool-down may extend an active wait but never reduces it.
