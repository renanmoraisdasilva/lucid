import type { ConversationGroup } from "../lib/grouping";

interface SidebarProps {
  groups: ConversationGroup[];
  hasConversations: boolean;
  currentId: string | null;
  hasMore: boolean;
  loadingMore: boolean;
  activeView: "chat" | "dashboard";
  open: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDashboard: () => void;
  onDelete: (id: string) => void;
  onLoadMore: () => void;
}

export function Sidebar({
  groups,
  hasConversations,
  currentId,
  hasMore,
  loadingMore,
  activeView,
  open,
  onClose,
  onSelect,
  onNew,
  onDashboard,
  onDelete,
  onLoadMore,
}: SidebarProps) {
  return (
    <aside
      id="app-sidebar"
      className={[
        "flex h-full w-[260px] shrink-0 flex-col border-r border-surface-border bg-surface-sidebar",
        "fixed inset-y-0 left-0 z-40 transition-transform lg:static lg:z-auto lg:translate-x-0 lg:visible",
        open ? "translate-x-0 shadow-2xl" : "invisible -translate-x-full",
      ].join(" ")}
    >
      <div className="flex h-16 items-center gap-2 px-4">
        <span className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-amber-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-accent" />
        </span>
        <span className="text-[17px] font-semibold tracking-tight">Lucid</span>
        <span className="ml-1 rounded border border-surface-border bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
          v0.1
        </span>
        {open ? (
          <button
            type="button"
            aria-label="Close navigation"
            onClick={onClose}
            className="ml-auto rounded-md p-1.5 text-[13px] text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary lg:hidden"
          >
            ×
          </button>
        ) : null}
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

      <div className="px-3 pb-2">
        <button
          type="button"
          onClick={onDashboard}
          aria-current={activeView === "dashboard" ? "page" : undefined}
          className={[
            "flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-[13px] transition-colors",
            activeView === "dashboard"
              ? "border border-surface-border-subtle/80 bg-surface-elevated font-medium text-text-primary"
              : "text-text-secondary hover:bg-surface-elevated/40 hover:text-text-primary",
          ].join(" ")}
        >
          <span
            aria-hidden="true"
            className={[
              "h-1.5 w-1.5 shrink-0 rounded-full",
              activeView === "dashboard" ? "bg-amber-accent" : "bg-surface-border-subtle",
            ].join(" ")}
          />
          <span>Dashboard</span>
        </button>
      </div>

      <div className="px-4">
        <div className="h-px bg-surface-border" />
      </div>

      <nav aria-label="Conversations" className="flex-1 overflow-y-auto px-2 pt-2">
        {!hasConversations ? (
          <p className="px-3 py-6 text-center text-[12px] leading-relaxed text-text-muted">
            No conversations yet. Sending your first message creates one.
          </p>
        ) : (
          <div className="space-y-4">
            {groups.map((group) => (
              <div key={group.label} className="space-y-1">
                <p className="px-2 py-1 text-[11px] font-medium text-text-muted">{group.label}</p>
                <ul className="space-y-0.5">
                  {group.items.map((conversation) => {
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
              </div>
            ))}

            {loadingMore ? (
              <div className="space-y-1 px-1" aria-hidden="true">
                {[0, 1].map((row) => (
                  <div key={row} className="h-7 animate-pulse rounded-md bg-surface-elevated/60" />
                ))}
              </div>
            ) : null}

            {hasMore ? (
              <button
                type="button"
                onClick={onLoadMore}
                disabled={loadingMore}
                className="w-full rounded-md px-2 py-1.5 text-[12px] text-text-muted transition-colors hover:bg-surface-elevated/40 hover:text-text-secondary disabled:opacity-50"
              >
                Load older conversations
              </button>
            ) : (
              <p className="border-t border-surface-border pt-3 text-center text-[11px] text-text-muted">
                You&apos;re all caught up
              </p>
            )}
          </div>
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
