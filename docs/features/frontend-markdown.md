---
id: UI-MARKDOWN-001
title: Safe Markdown rendering
paths:
  - frontend/src/components/Markdown.tsx
verificationMethod: automated-test
---

# Safe Markdown rendering

## Overview

Renders assistant Markdown with syntax highlighting while stripping raw HTML
and unsafe links, and copies code without the line-number gutter.
