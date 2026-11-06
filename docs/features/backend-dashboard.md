---
id: LUCID-DASH-001
title: Dashboard aggregation
paths:
  - backend/src/lucid/application/dashboard/**
links:
  - docs/archive/specs/002-lucid-dashboard-spec.md
verificationMethod: automated-test
---

# Dashboard aggregation

## Overview

Assembles overview metrics, token trends, latency percentiles, and recent
generation rows from stored attempts. The original dashboard specification is
archived at `docs/archive/specs/002-lucid-dashboard-spec.md`.

### [LUCID-DASH-RULE-001] The selected window controls every bucket
The 24h, 7d, and 30d ranges produce their documented bucket boundaries. Timestamps
are normalized to UTC before bucketing.

### [LUCID-DASH-RULE-002] Success rate uses only terminal attempts
Running or interrupted attempts do not count as success or failure when the
success rate is calculated.

### [LUCID-DASH-RULE-003] p95 needs enough samples
The p95 latency is reported only when the range contains at least 20 timed
attempts; otherwise the API says the sample is too small.

### [LUCID-DASH-RULE-004] Trends include empty buckets
A range with no attempts still returns every bucket, with real zeros kept
distinct from unavailable token data.

### [LUCID-DASH-RULE-005] Cost is unavailable without prices
When list prices are not configured, the cost fields are unavailable rather than
reported as zero.
