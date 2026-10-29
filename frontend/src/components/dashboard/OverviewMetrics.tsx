import type { DashboardOverview } from "../../api/types";
import { formatCost, formatCount, formatPercent, formatTokens } from "../../lib/dashboard-format";

function Metric({
  label,
  value,
  detail,
  accent = false,
}: {
  label: string;
  value: string;
  detail: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-elevated/40 p-3.5">
      <span className="text-[10px] font-medium uppercase leading-tight tracking-wider text-text-muted">
        {label}
      </span>
      <div
        className={[
          "mt-2 text-[24px] font-semibold leading-none tracking-tight tabular-nums",
          accent ? "text-amber-accent" : "text-text-primary",
        ].join(" ")}
      >
        {value}
      </div>
      <div className="mt-1.5 text-[11px] text-text-secondary">{detail}</div>
    </div>
  );
}

export function OverviewMetrics({ overview }: { overview: DashboardOverview }) {
  const usageDetail = overview.usage_partial ? "partial · usage missing" : "provider-reported";
  const hasPricing = overview.pricing.available && overview.estimated_cost_usd !== null;

  return (
    <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4 xl:grid-cols-7">
      <Metric
        label="Conversations"
        value={formatCount(overview.conversations_active)}
        detail={`${overview.conversations_new} new in range`}
      />
      <Metric
        label="User messages"
        value={formatCount(overview.user_messages)}
        detail="In the selected range"
      />
      <Metric
        label="Attempts"
        value={formatCount(overview.attempts)}
        detail={`${overview.failed} failed · ${overview.interrupted} interrupted`}
      />
      <Metric
        label="Success rate"
        value={formatPercent(overview.success_rate)}
        detail={
          overview.attempts === 0
            ? "No terminal attempts"
            : `${overview.completed} of ${overview.attempts} completed`
        }
        accent
      />
      <Metric
        label="Input tokens"
        value={formatTokens(overview.input_tokens)}
        detail={usageDetail}
      />
      <Metric
        label="Output tokens"
        value={formatTokens(overview.output_tokens)}
        detail={usageDetail}
      />
      <Metric
        label="Estimated cost"
        value={hasPricing ? formatCost(overview.estimated_cost_usd) : "Unavailable"}
        detail={
          hasPricing
            ? overview.pricing.free_tier
              ? "list price · free tier"
              : "estimate"
            : "pricing not configured"
        }
        accent={hasPricing}
      />
    </div>
  );
}
