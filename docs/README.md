# Documentation

This folder answers five questions. If a document does not fit one of them, it
probably belongs in `archive/` or in the root `README.md`.

| Question | Document |
| --- | --- |
| What behavior must exist today? | [`features/`](features/) |
| Why did we choose this? | [`decisions/`](decisions/) |
| How is it put together? | [`architecture.md`](architecture.md) |
| How do I test and verify it? | [`testing.md`](testing.md) |
| What are we doing next? | `plans/` — create it only when a plan is active |

## Current documents

- **[`features/`](features/)** — the behavior registry. One document per
  capability; each document contains one or more rules such as
  `### [UI-CHAT-INPUT-001] ...`. There is no maximum rule count.
- **[`decisions/`](decisions/)** — ADRs: the choice, the alternatives, and the
  cost. Link to them from a feature rule when the reason is not obvious.
- **[`architecture.md`](architecture.md)** — request lifecycle, data model, SSE
  contract, provider boundary, failure semantics, deployment shape.
- **[`testing.md`](testing.md)** — test layers, commands, evidence, coverage, and
  quality gates.

## Historical documents

[`archive/`](archive/) holds superseded material: original specs, completed
plans, the build narrative, code-quality history, and Gemini adapter notes.
Nothing there is current truth. Use it for context, not for decisions.

## Outside docs

- `../ui-mockups/` — static design mockups.
- `../assets/` — images and the demo GIF.
- `../README.md` — product summary and quick start.
- `../AGENTS.md` — how an agent should work here.
