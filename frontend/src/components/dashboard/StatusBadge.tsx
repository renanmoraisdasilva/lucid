import type { AttemptStatus } from "../../api/types";

const STYLES: Record<AttemptStatus, { label: string; className: string; dotClassName: string }> = {
  completed: {
    label: "Completed",
    className: "border-surface-border-subtle bg-surface-elevated text-text-primary",
    dotClassName: "bg-text-secondary",
  },
  failed: {
    label: "Failed",
    className: "border-danger-border bg-danger-dim text-danger",
    dotClassName: "bg-danger",
  },
  interrupted: {
    label: "Interrupted",
    className: "border-amber-border bg-amber-dim text-amber-accent",
    dotClassName: "bg-amber-accent",
  },
  in_progress: {
    label: "In progress",
    className: "border-surface-border bg-surface-elevated text-text-secondary",
    dotClassName: "bg-amber-accent animate-pulse",
  },
};

export function StatusBadge({ status }: { status: AttemptStatus }) {
  const style = STYLES[status];

  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-medium ${style.className}`}
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${style.dotClassName}`} />
      {style.label}
    </span>
  );
}
