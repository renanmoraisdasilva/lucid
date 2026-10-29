import type { DashboardBucket, DashboardLatencyStats, DashboardTrendPoint } from "../../api/types";
import {
  axisTicks,
  buildLinePath,
  buildSegments,
  selectedIndices,
  seriesMax,
} from "../../lib/chart";
import { bucketLabel, formatAxisMs, formatMs } from "../../lib/dashboard-format";
import { ChartFrame } from "./ChartFrame";

export function LatencyChart({
  kind,
  points,
  stats,
  bucket,
}: {
  kind: "ttft" | "duration";
  points: DashboardTrendPoint[];
  stats: DashboardLatencyStats;
  bucket: DashboardBucket;
}) {
  const p50 = (point: DashboardTrendPoint) =>
    kind === "ttft" ? point.ttft_ms_p50 : point.duration_ms_p50;
  const p95 = (point: DashboardTrendPoint) =>
    kind === "ttft" ? point.ttft_ms_p95 : point.duration_ms_p95;

  const segments50 = buildSegments(points, p50);
  const segments95 = buildSegments(points, p95);
  const max = Math.max(seriesMax(points.flatMap((point) => [p50(point), p95(point)])), 1_000);
  const yTicks = axisTicks(max, 4)
    .reverse()
    .map((value) => ({ value: value / max, label: formatAxisMs(value) }));
  const xLabels = selectedIndices(points.length).map((index) => ({
    index,
    label: bucketLabel(points[index].bucket_start, bucket),
  }));

  const title = kind === "ttft" ? "Time to first token" : "Generation duration";
  const p95Note =
    stats.samples === 0
      ? "No timed attempts in this range."
      : stats.p95_ms === null
        ? "p95 needs at least 20 samples."
        : null;

  return (
    <section className="rounded-xl border border-surface-border bg-surface-elevated/40 p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-[14px] font-semibold text-text-primary">{title}</h3>
          <p className="mt-0.5 text-[11px] text-text-secondary">
            Median and p95 per {bucket === "hour" ? "hour" : "day"}
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px]">
          <span className="flex items-center gap-1.5 text-text-primary">
            <span className="h-0.5 w-2.5 rounded-full bg-amber-accent" />
            p50
          </span>
          <span className="flex items-center gap-1.5 text-text-secondary">
            <span className="h-0.5 w-2.5 rounded-full bg-text-secondary" />
            p95
          </span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-surface-border bg-surface-bg/50 px-3 py-2 text-[11px]">
        <span className="text-text-muted">Period median</span>
        <span className="font-mono text-text-primary">{formatMs(stats.p50_ms)}</span>
        <span className="text-text-muted">p95</span>
        <span className="font-mono text-text-primary">{formatMs(stats.p95_ms)}</span>
        <span className="ml-auto text-text-muted">{stats.samples} samples</span>
      </div>

      <div className="mt-3">
        <ChartFrame
          yTicks={yTicks}
          xLabels={xLabels}
          pointCount={points.length}
          summary={`${title}: median and p95 per ${bucket}`}
        >
          <svg
            className="h-full w-full"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            {segments95.map((segment, index) => (
              <path
                key={`p95-${index}`}
                d={buildLinePath(segment, points.length, max)}
                className="text-text-secondary"
                fill="none"
                stroke="currentColor"
                strokeDasharray="3 3"
                strokeWidth="1.5"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
              />
            ))}
            {segments50.map((segment, index) => (
              <path
                key={`p50-${index}`}
                d={buildLinePath(segment, points.length, max)}
                className="text-amber-accent"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </svg>
        </ChartFrame>
      </div>

      {p95Note !== null ? <p className="mt-2 text-[11px] text-text-muted">{p95Note}</p> : null}
    </section>
  );
}
