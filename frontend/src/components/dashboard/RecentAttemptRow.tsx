import type { DashboardRecentAttempt } from "../../api/types";
import { formatAttemptTime, formatCount, formatMs, retrySummary } from "../../lib/dashboard-format";
import { StatusBadge } from "./StatusBadge";

function tokenValue(value: number | null): string {
  return value === null ? "—" : formatCount(value);
}

export function RecentAttemptRow({
  attempt,
  onSelect,
}: {
  attempt: DashboardRecentAttempt;
  onSelect: () => void;
}) {
  const retries = retrySummary(attempt.attempt_no, attempt.retry_count);

  return (
    <tr
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      aria-label={`Open details for ${attempt.conversation_title}`}
      className="cursor-pointer transition-colors hover:bg-surface-hover/40 focus-visible:bg-surface-hover/40"
    >
      <td className="whitespace-nowrap py-2.5 pl-4 pr-3 font-mono text-[11px] text-text-secondary">
        {formatAttemptTime(attempt.started_at)}
      </td>
      <td className="max-w-[220px] truncate py-2.5 pr-3 text-text-primary">
        {attempt.conversation_title}
      </td>
      <td className="py-2.5 pr-3">
        <StatusBadge status={attempt.status} />
      </td>
      <td className="whitespace-nowrap py-2.5 pr-3 font-mono text-[11px] text-text-muted">
        {attempt.model}
      </td>
      <td className="py-2.5 pr-3 text-right font-mono text-[11px] tabular-nums text-text-primary">
        {tokenValue(attempt.input_tokens)}
      </td>
      <td className="py-2.5 pr-3 text-right font-mono text-[11px] tabular-nums text-text-primary">
        {tokenValue(attempt.output_tokens)}
      </td>
      <td className="whitespace-nowrap py-2.5 pr-3 text-right font-mono text-[11px] tabular-nums text-text-primary">
        {formatMs(attempt.ttft_ms)}
      </td>
      <td className="whitespace-nowrap py-2.5 pr-3 text-right font-mono text-[11px] tabular-nums text-text-secondary">
        {formatMs(attempt.duration_ms)}
      </td>
      <td className="py-2.5 pr-4 text-center font-mono text-[11px] text-text-muted">
        #{attempt.attempt_no}
        {retries ? <span className="block text-[9px] text-amber-accent">{retries}</span> : null}
      </td>
    </tr>
  );
}
