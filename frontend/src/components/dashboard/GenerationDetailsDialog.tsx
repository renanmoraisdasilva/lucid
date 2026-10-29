import { useEffect, useId, useRef } from "react";

import type { DashboardRecentAttempt } from "../../api/types";
import { formatAttemptTime, formatCount, formatMs, retrySummary } from "../../lib/dashboard-format";
import { StatusBadge } from "./StatusBadge";

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface-bg/60 px-3 py-2">
      <dt className="text-[10px] uppercase tracking-wider text-text-muted">{label}</dt>
      <dd className="mt-0.5 truncate font-mono text-[12px] text-text-primary">{value}</dd>
    </div>
  );
}

function tokenValue(value: number | null): string {
  return value === null ? "—" : formatCount(value);
}

export function GenerationDetailsDialog({
  attempt,
  onClose,
}: {
  attempt: DashboardRecentAttempt;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const titleId = useId();
  const retries = retrySummary(attempt.attempt_no, attempt.retry_count);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
        className="max-h-[90vh] w-full max-w-[560px] overflow-y-auto rounded-xl border border-surface-border-subtle bg-surface-elevated p-5 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
              Generation details
            </span>
            <h2 id={titleId} className="mt-1 truncate text-[15px] font-semibold text-text-primary">
              {attempt.conversation_title}
            </h2>
            <p className="mt-0.5 font-mono text-[11px] text-text-muted">
              Attempt #{attempt.attempt_no}
              {retries ? ` · ${retries}` : ""} · {formatAttemptTime(attempt.started_at)}
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close generation details"
            className="rounded-lg border border-surface-border-subtle px-2.5 py-1 text-[12px] text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
          >
            Close
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <StatusBadge status={attempt.status} />
          <span className="font-mono text-[11px] text-text-secondary">{attempt.model}</span>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
          <Detail label="Input tokens" value={tokenValue(attempt.input_tokens)} />
          <Detail label="Output tokens" value={tokenValue(attempt.output_tokens)} />
          <Detail label="Context tokens" value={tokenValue(attempt.context_tokens)} />
          <Detail label="TTFT" value={formatMs(attempt.ttft_ms)} />
          <Detail label="Duration" value={formatMs(attempt.duration_ms)} />
          <Detail
            label="HTTP status"
            value={attempt.http_status === null ? "—" : String(attempt.http_status)}
          />
          <Detail
            label="Retries"
            value={attempt.retry_count === 0 ? "None" : `${attempt.retry_count} automatic`}
          />
          <Detail label="Attempt" value={`#${attempt.attempt_no}`} />
        </dl>

        {attempt.error_code !== null || attempt.error_message !== null ? (
          <div className="mt-4 rounded-lg border border-danger-border bg-danger-dim p-3">
            <p className="text-[10px] uppercase tracking-wider text-danger">Error</p>
            {attempt.error_code !== null ? (
              <p className="mt-1 font-mono text-[11px] text-danger">{attempt.error_code}</p>
            ) : null}
            {attempt.error_message !== null ? (
              <p className="mt-1 text-[12px] leading-relaxed text-text-secondary">
                {attempt.error_message}
              </p>
            ) : null}
          </div>
        ) : null}

        <p className="mt-4 text-[11px] text-text-muted">
          Metadata only — no prompts or message content are stored or shown here.
        </p>
      </div>
    </div>
  );
}
