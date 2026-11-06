---
id: LUCID-CTX-001
title: Conversation context budgeting
paths:
  - backend/src/lucid/application/context.py
  - backend/src/lucid/application/prompts.py
links:
  - docs/archive/specs/001-lucid-specification.md
verificationMethod: automated-test
---

# Conversation context budgeting

## Overview

Builds the prompt from the conversation history within the model's context
budget. The original specification is archived at
`docs/archive/specs/001-lucid-specification.md`.

### [LUCID-CTX-RULE-001] The newest message always fits
The newest user message is never dropped. If it alone exceeds the available
budget, the request is rejected instead of silently truncating it.

### [LUCID-CTX-RULE-002] Oldest messages are dropped first
When the history does not fit, the oldest messages are removed before newer
ones. A leading assistant message left behind by the cut is dropped too.

### [LUCID-CTX-RULE-003] Empty or assistant-ending histories are rejected
A request with no messages, or one whose history ends with an assistant turn,
is rejected before a provider call.

### [LUCID-CTX-RULE-004] System prompt and per-message overhead count
The system prompt and the per-message overhead are included in the budget. They
are not treated as free space.

### [LUCID-CTX-RULE-005] Reserved output is excluded from the history budget
The output token reservation is subtracted before history is selected, so the
model has room to answer.
