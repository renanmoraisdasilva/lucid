import type { ConversationSummary } from "../api/types";

interface SidebarProps {
  conversations: ConversationSummary[];
  currentId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export function Sidebar({ conversations, currentId, onSelect, onNew, onDelete }: SidebarProps) {
  return (
    <aside className="flex h-full w-[260px] shrink-0 flex-col border-r border-surface-border bg-surface-sidebar">
      <div className="flex h-16 items-center gap-2 px-4">
        <span className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-amber-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-accent" />
        </span>
        <span className="text-[17px] font-semibold tracking-tight">Lucid</span>
        <span className="ml-1 rounded border border-surface-border bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
          v0.1
        </span>
      </div>

      <div className="px-3 pb-2">
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center justify-between rounded-lg border border-surface-border-subtle bg-surface-elevated px-3 py-2 text-[13px] font-medium transition-colors hover:bg-surface-hover"
        >
          <span className="flex items-center gap-2">
            <span aria-hidden="true" className="text-text-secondary">
              +
            </span>
            New chat
          </span>
          <kbd className="rounded border border-surface-border bg-surface-sidebar px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
            Ctrl K
          </kbd>
        </button>
      </div>

      <nav aria-label="Conversations" className="flex-1 overflow-y-auto px-2 pt-2">
        {conversations.length === 0 ? (
          <p className="px-3 py-6 text-center text-[12px] leading-relaxed text-text-muted">
            No conversations yet. Sending your first message creates one.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((conversation) => {
              const active = conversation.id === currentId;
              return (
                <li key={conversation.id} className="group flex items-center gap-1 pr-1">
                  <button
                    type="button"
                    onClick={() => onSelect(conversation.id)}
                    aria-current={active ? "page" : undefined}
                    className={[
                      "flex min-w-0 flex-1 items-center gap-2 rounded-md py-1.5 pl-2.5 text-left text-[13px] transition-colors",
                      active
                        ? "border border-surface-border-subtle/80 bg-surface-elevated font-medium text-text-primary"
                        : "text-text-secondary hover:bg-surface-elevated/40 hover:text-text-primary",
                    ].join(" ")}
                  >
                    <span
                      aria-hidden="true"
                      className={[
                        "h-1.5 w-1.5 shrink-0 rounded-full",
                        active ? "bg-amber-accent" : "bg-surface-border-subtle",
                      ].join(" ")}
                    />
                    <span className="truncate">{conversation.title}</span>
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete conversation ${conversation.title}`}
                    onClick={() => onDelete(conversation.id)}
                    className="rounded p-1 text-text-muted opacity-0 transition-opacity hover:text-danger focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    ×
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </nav>

      <div className="flex items-center gap-2.5 border-t border-surface-border p-3">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-surface-hover text-[12px] font-medium">
          R
        </span>
        <span className="truncate text-[13px] font-medium">Renan</span>
      </div>
    </aside>
  );
}
