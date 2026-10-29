import type { DashboardRecentAttempt } from "../../api/types";
import { RecentAttemptRow } from "./RecentAttemptRow";

const COLUMNS = [
  { label: "Time", align: "left" },
  { label: "Conversation", align: "left" },
  { label: "Status", align: "left" },
  { label: "Model", align: "left" },
  { label: "In", align: "right" },
  { label: "Out", align: "right" },
  { label: "TTFT", align: "right" },
  { label: "Duration", align: "right" },
  { label: "Attempt", align: "center" },
] as const;

export function RecentAttemptsTable({
  attempts,
  onSelect,
}: {
  attempts: DashboardRecentAttempt[];
  onSelect: (attempt: DashboardRecentAttempt) => void;
}) {
  return (
    <div className="hidden overflow-x-auto rounded-xl border border-surface-border bg-surface-elevated/30 xl:block">
      <table className="w-full border-collapse text-left text-[12px]">
        <caption className="sr-only">Latest generation attempts</caption>
        <thead>
          <tr className="border-b border-surface-border text-[10px] uppercase tracking-wider text-text-muted">
            {COLUMNS.map((column, index) => (
              <th
                key={column.label}
                scope="col"
                className={`whitespace-nowrap py-2 font-medium ${
                  column.align === "right"
                    ? "pr-3 text-right"
                    : column.align === "center"
                      ? "pr-4 text-center"
                      : index === 0
                        ? "pl-4 pr-3"
                        : "pr-3"
                }`}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border">
          {attempts.map((attempt) => (
            <RecentAttemptRow
              key={attempt.attempt_id}
              attempt={attempt}
              onSelect={() => onSelect(attempt)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
