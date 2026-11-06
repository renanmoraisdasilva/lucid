---
id: LUCID-RETRY-001
title: Retry, backoff, and provider cool-down
paths:
  - backend/src/lucid/application/retry.py
  - backend/src/lucid/application/cooldown.py
  - backend/src/lucid/application/chat/retries.py
verificationMethod: automated-test
---

# Retry, backoff, and provider cool-down

## Overview

Decides whether a failed turn may be retried, applies backoff, and honours the
provider's cool-down hint without shortening an active wait.
