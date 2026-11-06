---
id: UI-DASH-001
title: Dashboard view
paths:
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/components/dashboard/**
  - frontend/src/hooks/useDashboard.ts
links:
  - docs/archive/specs/002-lucid-dashboard-spec.md
verificationMethod: automated-test
---

# Dashboard view

## Overview

Presents volume, success rate, tokens, latency percentiles, and per-attempt
details. The original dashboard specification is archived at
`docs/archive/specs/002-lucid-dashboard-spec.md`.

### [UI-DASH-RULE-001] Loading does not pretend to have data
While the dashboard loads, it announces loading and does not show fabricated
zero values.

### [UI-DASH-RULE-002] An empty range is explained
A range with no attempts explains that it is empty instead of showing a broken
chart.

### [UI-DASH-RULE-003] A failed request can be retried
When the dashboard request fails, the view offers a retry and keeps stale data
visible when it has it.

### [UI-DASH-RULE-004] Generation details show the attempt metadata
Opening a generation shows its model, status, tokens, timing, and error code,
without an error block for a completed attempt.

### [UI-DASH-RULE-005] A thin p95 sample is explained
When there are too few timed attempts, the latency view explains that p95 is
unavailable instead of showing a misleading value.
