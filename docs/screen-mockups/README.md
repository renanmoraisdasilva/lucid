# Screen mockups

Static HTML previews of the Lucid interface. They exist to settle layout and state
questions **before** React work starts, not to be copied into the app.

Open any file directly in a browser (`file://` works). They load Tailwind and fonts
from CDNs, so they need an internet connection; the real app does neither.

## Shared files

| File | Responsibility |
|---|---|
| `theme.js` | Design tokens. The only place colours and font families are defined. Loaded right after the Tailwind CDN. |
| `shell.js` | Sidebar, header, and composer markup. Renders from one source so every screen has identical chrome. |
| `theme.js` / `shell.js` are **not** shipped to production | The app expresses the same tokens through its Tailwind 4 build. |

Pages provide `#sidebar-mount`, `#header-mount`, `#composer-mount` and their own
`<main>`, then call:

```js
LucidShell.mount({ activeId: "evt", title: "…", streaming: false, groups: [...], sidebarExtra: "…" });
```

## Screens

| File | State | Spec reference |
|---|---|---|
| `home.html` | Conversation at rest: user turn, assistant Markdown, code block, table, usage counts | §5.1, §5.2, §5.7 |
| `new-chat.html` | Empty state, example prompts, no conversation record yet | §5.3 (create on first message) |
| `generating.html` | Streaming response, disabled composer, Stop action | §5.1, §5.5, §5.8 |
| `interrupted.html` | Partial output kept, `Interrupted` marker, Retry, usage unavailable | §5.5, §5.7, §5.8 |
| `failed.html` | Provider failure before any token, saved message, Retry with attempt counter | §5.8 |
| `delete-chat.html` | Permanent delete confirmation from the sidebar row | §5.3 |
| `sidebar-states.html` | Empty history, next page loading, end of list | §5.3 (pagination) |

A post-token failure combines `interrupted.html`'s partial text with `failed.html`'s
error card; the error card uses `danger` tokens, the interrupted marker uses `amber`.

## Tokens

Colours (defined in `theme.js`):

| Token | Value | Use |
|---|---|---|
| `surface-bg` | `#171512` | Page background |
| `surface-sidebar` | `#13120f` | Sidebar |
| `surface-elevated` | `#211e19` | Composer, active row, buttons, cards |
| `surface-code` | `#181613` | Code block body |
| `surface-border` | `#26221c` | Default borders and dividers |
| `surface-border-subtle` | `#38332b` | Emphasised borders (composer, active row) |
| `surface-hover` | `#2a2620` | Hover fill |
| `amber-accent` | `#e9a34b` | Primary action, active marker, links, bullet dots |
| `amber-hover` | `#f5b058` | Hover for primary action |
| `amber-dim` / `amber-border` | 15% / 30% amber | Interrupted badge, avatar ring |
| `danger` / `danger-dim` / `danger-border` | `#e2685c` + tints | Destructive action, failed generation |
| `text-primary` | `#f3eee5` | Body text |
| `text-secondary` | `#a8a094` | Supporting text |
| `text-muted` | `#736b60` | Metadata, timestamps, group labels |

Type and spacing conventions:

| Element | Convention |
|---|---|
| Brand | 17px / 600 |
| Header title | 14px / 500 |
| Assistant heading | 18px / 600, section 16px / 600 |
| Body | 15px / 1.6 (14px on small screens) |
| UI text | 13px |
| Metadata | 12px; monospace 11px for usage, shortcuts, attempt counters |
| Micro labels | 11px; 10px monospace for chips and `kbd` |
| Sidebar | 260px wide, 16px brand header, 6px row radius |
| Header | 56px tall, 1px bottom border |
| Content column | `max-w-3xl` (768px), 24–48px horizontal padding |
| Message rhythm | 28px between turns |
| Radius | 6px rows and small buttons, 8px buttons and inputs, 12px cards/code/modal, 16px composer and user bubble (top-right 4px) |

## Decisions these mockups encode

- **Assistant answers are editorial documents, not bubbles.** Users get bubbles; the
  assistant gets an avatar, a metadata row, and full-width Markdown. Spec §5.1 was
  amended accordingly.
- **No model badge and no latency.** Only `in / out` token counts, or
  `usage unavailable`. There is no model selector anywhere.
- **Timestamps only on user turns.** No author names: there is one user and no
  author column.
- **Enter sends, Shift+Enter adds a newline, Ctrl/⌘+K starts a new chat.**
- **Sidebar groups are derived from `updated_at`** (Today / Yesterday / Previous 7
  days), so grouping never contradicts "most recently updated first".
- **Code blocks have a language label and a copy button, no line-number gutter.**
- **Delete is the only destructive action**, exposed per row on hover and confirmed
  in a modal. There is no archive, no share, no export.
- **No search, attachments, web browsing, tuning, or knowledge base.** Those are
  explicit non-goals in spec §3 and were removed from earlier drafts of these files.

## Known gaps (deliberate)

- Loading skeletons for the first sidebar page are shown only for pagination; the
  initial load reuses the same pattern.
- Long-message trimming, request-size errors, and offline behaviour are not mocked.
- These pages are desktop-first; the shell collapses to an off-canvas sidebar below
  the `lg` breakpoint.
