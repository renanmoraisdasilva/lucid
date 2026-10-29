import type { DashboardRecentAttempt } from "../../api/types";
import {
  formatAttemptTime,
  formatMs,
  formatTokens,
  retrySummary,
} from "../../lib/dashboard-format";
import { StatusBadge } from "./StatusBadge";

export function RecentAttemptCard({
  attempt,
  onSelect,
}: {
  attempt: DashboardRecentAttempt;
  onSelect: () => void;
}) {
  const retries = retrySummary(attempt.attempt_no, attempt.retry_count);
  const hasUsage = attempt.input_tokens !== null || attempt.output_tokens !== null;

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-label={`Open details for ${attempt.conversation_title}`}
      className="w-full rounded-xl border border-surface-border bg-surface-elevated/40 p-4 text-left transition-colors hover:bg-surface-elevated/70"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-mono text-[11px] text-text-muted">
            {formatAttemptTime(attempt.started_at)}
          </div>
          <div className="mt-0.5 truncate text-[13px] font-medium text-text-primary">
            {attempt.conversation_title}
          </div>
        </div>
        <StatusBadge status={attempt.status} />
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 rounded-lg border border-surface-border bg-surface-bg/60 p-2.5 text-[11px]">
        <div>
          <span className="block text-text-muted">TTFT</span>
          <span className="font-mono text-text-primary">{formatMs(attempt.ttft_ms)}</span>
        </div>
        <div>
          <span className="block text-text-muted">Duration</span>
          <span className="font-mono text-text-primary">{formatMs(attempt.duration_ms)}</span>
        </div>
        <div>
          <span className="block text-text-muted">{hasUsage ? "Tokens" : "Retries"}</span>
          <span
            className={hasUsage ? "font-mono text-text-primary" : "font-mono text-amber-accent"}
          >
            {hasUsage
              ? `${formatTokens(attempt.input_tokens)} / ${formatTokens(attempt.output_tokens)}`
              : retries || "0"}
          </span>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-text-muted">
        <span className="truncate">
          {attempt.model} · attempt #{attempt.attempt_no}
          {retries ? ` · ${retries}` : ""}
        </span>
        <span className="inline-flex shrink-0 items-center gap-1 text-amber-accent">
          Details <span aria-hidden="true">→</span>
        </span>
      </div>

      {attempt.error_code !== null ? (
        <p className="mt-2 truncate font-mono text-[10px] text-danger">
          {attempt.error_code}
          {attempt.http_status !== null ? ` · ${attempt.http_status}` : ""}
        </p>
      ) : null}
    </button>
  );
}
