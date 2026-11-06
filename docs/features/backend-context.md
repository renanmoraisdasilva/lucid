---
id: LUCID-CTX-001
title: Conversation context budgeting
paths:
  - backend/src/lucid/application/context.py
  - backend/src/lucid/application/prompts.py
verificationMethod: automated-test
---

# Conversation context budgeting

## Overview

Builds the prompt from the conversation history within the model's context
budget, dropping the oldest messages first while keeping the newest turn.
