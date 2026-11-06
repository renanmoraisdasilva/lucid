---
id: UI-CHAT-001
title: Chat, composer, and message presentation
paths:
  - frontend/src/App.tsx
  - frontend/src/hooks/chat/**
  - frontend/src/components/Composer.tsx
  - frontend/src/components/MessageList.tsx
verificationMethod: automated-test
---

# Chat, composer, and message presentation

## Overview

Owns the chat shell: sending, streaming, stopping, retrying, focus management,
and the visible state of a message while it is generating or interrupted.
