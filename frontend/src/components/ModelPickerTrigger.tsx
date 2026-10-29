import type { KeyboardEvent, RefObject } from "react";

interface ModelPickerTriggerProps {
  triggerRef: RefObject<HTMLButtonElement | null>;
  name: string;
  endpoint: string | null;
  open: boolean;
  disabled: boolean;
  listboxId: string;
  onToggle: () => void;
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
}

export function ModelPickerTrigger({
  triggerRef,
  name,
  endpoint,
  open,
  disabled,
  listboxId,
  onToggle,
  onKeyDown,
}: ModelPickerTriggerProps) {
  return (
    <button
      ref={triggerRef}
      type="button"
      disabled={disabled}
      aria-haspopup="listbox"
      aria-expanded={open}
      aria-controls={open ? listboxId : undefined}
      aria-label={`Model: ${name}${endpoint === null ? "" : ` (${endpoint})`}`}
      onClick={onToggle}
      onKeyDown={onKeyDown}
      className="flex max-w-[10rem] items-center gap-1.5 rounded-full border border-surface-border-subtle bg-transparent py-1 pl-2.5 pr-2 font-mono text-[11px] text-text-secondary transition-colors hover:border-amber-border hover:text-text-primary focus-visible:border-amber-border focus-visible:text-text-primary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-surface-border-subtle disabled:hover:text-text-secondary sm:max-w-[16rem]"
    >
      <span className="truncate">{name}</span>
      {endpoint === null ? null : <span className="shrink-0 text-text-muted">{endpoint}</span>}
      <svg
        aria-hidden="true"
        viewBox="0 0 12 12"
        className={[
          "h-2.5 w-2.5 shrink-0 text-text-muted transition-transform",
          open ? "rotate-180" : "",
        ].join(" ")}
      >
        <path d="M2 4.5 6 8.5 10 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </button>
  );
}
