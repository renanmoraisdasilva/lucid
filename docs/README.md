# Documentation

Lucid was built from a specification, and the documents are part of the deliverable. They are split by the question they answer, so nobody has to read a 45,000-character plan to find out how streaming works.

## Read this first

| If you want to… | Read |
| --- | --- |
| understand the product in five minutes | [README](../README.md) |
| understand how it is put together | [Architecture](architecture.md) |
| judge the tests | [Testing](testing.md) |
| judge the code quality claims | [Code quality](code-quality.md) |
| see how the project was run | [How this was built](how-it-was-built.md) |
| read a specific decision | [ADRs](decisions/) |

## Current documents

These describe the system as it is today.

| Document | What it answers |
| --- | --- |
| [`architecture.md`](architecture.md) | Request lifecycle, data model, SSE contract, provider boundary, failure semantics, dashboard telemetry, deployment shape, known gaps |
| [`testing.md`](testing.md) | What each test layer proves, the counts, how to run everything, what is deliberately untested |
| [`code-quality.md`](code-quality.md) | The gates, the enforced budgets, and the refactors they forced |
| [`screen-mockups/`](screen-mockups/README.md) | The static design pass: every screen state as HTML, with the shared tokens and shell |
| [`decisions/`](decisions/) | Seven ADRs: provider, data model, streaming, identifiers, failures, frontend, model selection |

## Historical records

These were authoritative when written and are kept as they were. Amendments are appended, never rewritten — that is the point of a record.

| Document | Status |
| --- | --- |
| [`specs/001-lucid-specification.md`](specs/001-lucid-specification.md) | Requirements and acceptance criteria, v0.1 → v0.5. The earlier sections describe the single-provider MVP; §5.4 and §6.1 carry the v0.5 amendment. |
| [`specs/002-lucid-dashboard-spec.md`](specs/002-lucid-dashboard-spec.md) | Dashboard requirements and acceptance criteria. |
| [`plans/implementation-plan.md`](plans/implementation-plan.md) | The original build plan: milestones, DDL, API and SSE contracts. Superseded in places by ADR-007, with an amendment at the top saying which. |
| [`plans/dashboard-implementation-plan.md`](plans/dashboard-implementation-plan.md) | Dashboard milestones and file inventory. |
| [`plans/code-health-budget.md`](plans/code-health-budget.md) | The measurement that set the limits, plus the plan to get under them. Still the reference for the numbers. |
| [`architecture/gemini-adapter-notes.md`](architecture/gemini-adapter-notes.md) | Verified SDK behaviour while building the Gemini adapter: event shapes, error mapping, transport quirks. Useful if that adapter is ever touched again. |

When a historical document disagrees with [`architecture.md`](architecture.md), the architecture document is right and the ADR explains why.

## Conventions

- **Specs** say *what must be true*, including non-goals and acceptance criteria.
- **ADRs** say *why this way and not the other*, with rejected alternatives and their costs.
- **Plans** say *in what order* and *how done is proven*.
- **Architecture** says *how it works now*. It is the only document allowed to describe the present without a date qualifier.
