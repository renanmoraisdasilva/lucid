import type { DashboardBucket, DashboardLatency, DashboardTrendPoint } from "../../api/types";
import { LatencyChart } from "./LatencyChart";
import { ReliabilityChart } from "./ReliabilityChart";
import { TokenTrendChart } from "./TokenTrendChart";

export function TrendsSection({
  trend,
  latency,
  bucket,
  inputTotal,
  outputTotal,
}: {
  trend: DashboardTrendPoint[];
  latency: DashboardLatency;
  bucket: DashboardBucket;
  inputTotal: number | null;
  outputTotal: number | null;
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
            02 / Trends
          </span>
          <h2 className="mt-1 text-[15px] font-semibold tracking-tight text-text-primary sm:text-[16px]">
            Tokens, latency, and reliability
          </h2>
        </div>
        <span className="text-[11px] text-text-muted">
          Hourly for 24h · daily for 7 and 30 days
        </span>
      </div>

      <TokenTrendChart
        points={trend}
        bucket={bucket}
        inputTotal={inputTotal}
        outputTotal={outputTotal}
      />

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <LatencyChart kind="ttft" points={trend} stats={latency.ttft} bucket={bucket} />
        <LatencyChart kind="duration" points={trend} stats={latency.duration} bucket={bucket} />
      </div>

      <ReliabilityChart points={trend} bucket={bucket} />
    </section>
  );
}
