---
id: UI-MARKDOWN-001
title: Safe Markdown rendering
paths:
  - frontend/src/components/Markdown.tsx
verificationMethod: automated-test
---

# Safe Markdown rendering

## Overview

Renders assistant Markdown with syntax highlighting while removing unsafe HTML
and links.

### [UI-MARKDOWN-RULE-001] Markdown structure is rendered
Headings, lists, tables, and fenced code are rendered from assistant Markdown.

### [UI-MARKDOWN-RULE-002] Raw HTML and embedded frames are removed
Scripts, iframes, and other raw HTML are not rendered.

### [UI-MARKDOWN-RULE-003] Unsafe links are neutralized
A `javascript:` link does not become a working link.

### [UI-MARKDOWN-RULE-004] Code copies without the line-number gutter
Copying a code block includes the code, not the visible line numbers.
