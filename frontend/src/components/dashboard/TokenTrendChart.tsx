import { useId } from "react";

import type { DashboardBucket, DashboardTrendPoint } from "../../api/types";
import {
  axisTicks,
  buildAreaPath,
  buildLinePath,
  buildSegments,
  selectedIndices,
  seriesMax,
} from "../../lib/chart";
import { bucketLabel, formatCompactNumber, formatTokens } from "../../lib/dashboard-format";
import { ChartFrame } from "./ChartFrame";

export function TokenTrendChart({
  points,
  bucket,
  inputTotal,
  outputTotal,
}: {
  points: DashboardTrendPoint[];
  bucket: DashboardBucket;
  inputTotal: number | null;
  outputTotal: number | null;
}) {
  const gradientId = `token-fill-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const inputSegments = buildSegments(points, (point) => point.input_tokens);
  const outputSegments = buildSegments(points, (point) => point.output_tokens);
  const max = Math.max(
    seriesMax(points.flatMap((point) => [point.input_tokens, point.output_tokens])),
    1_000,
  );
  const yTicks = axisTicks(max, 4)
    .reverse()
    .map((value) => ({ value: value / max, label: formatCompactNumber(value) }));
  const xLabels = selectedIndices(points.length).map((index) => ({
    index,
    label: bucketLabel(points[index].bucket_start, bucket),
  }));

  return (
    <section className="rounded-xl border border-surface-border bg-surface-elevated/40 p-4 sm:p-5">
      <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
        <div>
          <h3 className="text-[14px] font-semibold text-text-primary">Token usage</h3>
          <p className="mt-0.5 text-[11px] text-text-secondary">
            Input and output tokens per {bucket === "hour" ? "hour" : "day"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-[11px]">
          <span className="flex items-center gap-1.5 text-text-primary">
            <span className="h-0.5 w-2.5 rounded-full bg-amber-accent" />
            Input <span className="font-mono text-text-muted">{formatTokens(inputTotal)}</span>
          </span>
          <span className="flex items-center gap-1.5 text-text-secondary">
            <span className="h-0.5 w-2.5 rounded-full bg-text-secondary" />
            Output <span className="font-mono text-text-muted">{formatTokens(outputTotal)}</span>
          </span>
        </div>
      </div>

      <div className="mt-4">
        <ChartFrame
          yTicks={yTicks}
          xLabels={xLabels}
          pointCount={points.length}
          summary={`Input and output tokens per ${bucket}`}
        >
          <svg
            className="h-full w-full"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <defs>
              <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--color-amber-accent)" stopOpacity="0.22" />
                <stop offset="100%" stopColor="var(--color-amber-accent)" stopOpacity="0" />
              </linearGradient>
            </defs>

            {inputSegments.map((segment, index) => (
              <g key={`input-${index}`} className="text-amber-accent">
                <path d={buildAreaPath(segment, points.length, max)} fill={`url(#${gradientId})`} />
                <path
                  d={buildLinePath(segment, points.length, max)}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  vectorEffect="non-scaling-stroke"
                />
              </g>
            ))}

            {outputSegments.map((segment, index) => (
              <path
                key={`output-${index}`}
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
          </svg>
        </ChartFrame>
      </div>

      <p className="mt-2 text-[11px] text-text-muted">
        A gap means usage was unavailable; a line at zero is a real zero.
      </p>
    </section>
  );
}
