import { useEffect, useState } from "react";

import type { DashboardRange } from "../../api/types";
import { RANGE_LABELS, formatUpdated } from "../../lib/dashboard-format";
import { RangeSelector } from "./RangeSelector";

interface DashboardToolbarProps {
  range: DashboardRange;
  onRangeChange: (range: DashboardRange) => void;
  updatedAt: number;
  fetching: boolean;
  onRefresh: () => void;
}

export function DashboardToolbar({
  range,
  onRangeChange,
  updatedAt,
  fetching,
  onRefresh,
}: DashboardToolbarProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 5_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-wrap items-center gap-3">
        <RangeSelector value={range} onChange={onRangeChange} />
        <span className="text-[11px] text-text-muted">{RANGE_LABELS[range]}</span>
      </div>

      <div className="flex items-center gap-3">
        <span aria-live="polite" className="font-mono text-[11px] text-text-muted">
          {formatUpdated(updatedAt, now)} · auto 20s
        </span>
        <button
          type="button"
          onClick={onRefresh}
          disabled={fetching}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-surface-border-subtle bg-surface-elevated px-3 text-[12px] font-medium text-text-primary transition-colors hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span aria-hidden="true">↻</span>
          {fetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>
    </div>
  );
}
