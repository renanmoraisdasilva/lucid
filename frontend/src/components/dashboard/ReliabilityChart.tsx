import type { DashboardBucket, DashboardTrendPoint } from "../../api/types";
import { selectedIndices, xPercent } from "../../lib/chart";
import { bucketLabel } from "../../lib/dashboard-format";

export function ReliabilityChart({
  points,
  bucket,
}: {
  points: DashboardTrendPoint[];
  bucket: DashboardBucket;
}) {
  const totals = points.reduce(
    (sum, point) => ({
      completed: sum.completed + point.completed,
      failed: sum.failed + point.failed,
      interrupted: sum.interrupted + point.interrupted,
    }),
    { completed: 0, failed: 0, interrupted: 0 },
  );
  const maxAttempts = Math.max(2, ...points.map((point) => point.attempts));
  const xLabels = selectedIndices(points.length);

  return (
    <section className="rounded-xl border border-surface-border bg-surface-elevated/40 p-4 sm:p-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <h3 className="text-[14px] font-semibold text-text-primary">Reliability</h3>
          <p className="mt-0.5 text-[11px] text-text-secondary">
            Terminal outcomes per {bucket === "hour" ? "hour" : "day"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-[11px]">
          <span className="flex items-center gap-1.5 text-text-secondary">
            <span className="h-2 w-2 rounded-sm bg-text-muted" />
            Completed <span className="font-mono text-text-muted">{totals.completed}</span>
          </span>
          <span className="flex items-center gap-1.5 text-danger">
            <span className="h-2 w-2 rounded-sm bg-danger" />
            Failed <span className="font-mono text-text-muted">{totals.failed}</span>
          </span>
          <span className="flex items-center gap-1.5 text-amber-accent">
            <span className="h-2 w-2 rounded-sm bg-amber-accent" />
            Interrupted <span className="font-mono text-text-muted">{totals.interrupted}</span>
          </span>
        </div>
      </div>

      <div className="mt-4 flex">
        <div
          className="flex h-40 w-9 shrink-0 flex-col justify-between pr-1.5 text-right font-mono text-[9px] leading-none text-text-muted"
          aria-hidden="true"
        >
          <span>{maxAttempts}</span>
          <span>{Math.ceil(maxAttempts / 2)}</span>
          <span>0</span>
        </div>

        <div className="relative h-40 min-w-0 flex-1" role="img" aria-label="Attempts by outcome">
          <div className="absolute inset-x-0 top-0 border-t border-dashed border-surface-border/70" />
          <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-surface-border/70" />
          <div className="absolute inset-x-0 bottom-0 border-t border-surface-border" />

          <div className="absolute inset-0 flex items-end gap-px">
            {points.map((point) => {
              const label = bucketLabel(point.bucket_start, bucket);
              const detail = `${label}: ${point.completed} completed, ${point.failed} failed, ${point.interrupted} interrupted`;
              return (
                <div
                  key={point.bucket_start}
                  title={detail}
                  className="flex h-full min-w-0 flex-1 flex-col justify-end"
                >
                  {point.attempts === 0 ? (
                    <div className="h-0.5 w-full bg-surface-border" />
                  ) : (
                    <div
                      className="flex w-full flex-col-reverse overflow-hidden rounded-sm"
                      style={{ height: `${(point.attempts / maxAttempts) * 100}%` }}
                    >
                      <div
                        className="bg-text-muted"
                        style={{ height: `${(point.completed / point.attempts) * 100}%` }}
                      />
                      <div
                        className="bg-danger"
                        style={{ height: `${(point.failed / point.attempts) * 100}%` }}
                      />
                      <div
                        className="bg-amber-accent"
                        style={{ height: `${(point.interrupted / point.attempts) * 100}%` }}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="relative ml-9 mt-1 h-3">
        {xLabels.map((index) => {
          const transform =
            points.length <= 1
              ? "translateX(-50%)"
              : index === 0
                ? "translateX(0)"
                : index === points.length - 1
                  ? "translateX(-100%)"
                  : "translateX(-50%)";
          return (
            <span
              key={points[index].bucket_start}
              className="absolute top-0 whitespace-nowrap font-mono text-[9px] text-text-muted"
              style={{ left: `${xPercent(index, points.length)}%`, transform }}
            >
              {bucketLabel(points[index].bucket_start, bucket)}
            </span>
          );
        })}
      </div>

      <p className="mt-2 text-[11px] text-text-muted">
        Zero attempts are shown at the baseline, not treated as missing data.
      </p>
    </section>
  );
}
