---
id: UI-CHAT-001
title: Chat, composer, and message presentation
paths:
  - frontend/src/App.tsx
  - frontend/src/hooks/chat/**
  - frontend/src/hooks/useChat.ts
  - frontend/src/components/Composer.tsx
  - frontend/src/components/MessageList.tsx
  - frontend/src/components/chat/**
links:
  - docs/decisions/ADR-006-frontend-and-local-dev.md
verificationMethod: automated-test
---

# Chat, composer, and message presentation

## Overview

Owns the chat shell: sending, streaming, stopping, retrying, focus management,
and the visible state of a message while it is generating or interrupted.

### [UI-CHAT-INPUT-001] A pending response disables the composer
While a response is streaming, the composer is disabled and a second send is
not possible.

### [UI-CHAT-INPUT-002] The composer returns to idle after the stream ends
When the response finishes, the composer becomes usable again, including after a
StrictMode remount.

### [UI-CHAT-SEND-001] The selected model is sent with the message
Each message carries the model the user selected, not a global default.

### [UI-CHAT-RETRY-001] Retry reuses the failed user message
A failed user message offers Retry, and retrying sends the same message again
without creating a second user message.

### [UI-CHAT-STOP-001] Stopping keeps the partial response
When the user stops a generation, the text already received stays visible and
the message is marked interrupted.
