import type { DashboardOverview } from "../../api/types";
import { formatCount, formatTokens } from "../../lib/dashboard-format";

function TokenCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-elevated/40 p-3.5">
      <span className="text-[10px] font-medium uppercase tracking-wider text-text-muted">
        {label}
      </span>
      <div className="mt-2 text-[22px] font-semibold leading-none tracking-tight tabular-nums text-text-primary">
        {value}
      </div>
      <div className="mt-1.5 text-[11px] text-text-secondary">{detail}</div>
    </div>
  );
}

export function TokenUsageSummary({ overview }: { overview: DashboardOverview }) {
  const detail = overview.usage_partial ? "partial · usage missing" : "provider-reported";
  const average = (value: number | null) => (value === null ? "—" : formatCount(value));

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
            03 / Token usage
          </span>
          <h2 className="mt-1 text-[15px] font-semibold tracking-tight text-text-primary sm:text-[16px]">
            Totals and averages
          </h2>
        </div>
        <span className="text-[11px] text-text-muted">Provider-reported usage only</span>
      </div>

      <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <TokenCard
          label="Total input"
          value={formatTokens(overview.input_tokens)}
          detail={detail}
        />
        <TokenCard
          label="Total output"
          value={formatTokens(overview.output_tokens)}
          detail={detail}
        />
        <TokenCard
          label="Average input"
          value={average(overview.average_input_tokens)}
          detail="Per generation with usage"
        />
        <TokenCard
          label="Average output"
          value={average(overview.average_output_tokens)}
          detail="Per generation with usage"
        />
      </div>
    </section>
  );
}
