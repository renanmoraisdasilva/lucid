import type { ReactNode } from "react";

import { xPercent } from "../../lib/chart";

interface YTick {
  value: number;
  label: string;
}

interface XLabel {
  index: number;
  label: string;
}

interface ChartFrameProps {
  heightClass?: string;
  yTicks: YTick[];
  xLabels: XLabel[];
  pointCount: number;
  summary: string;
  children: ReactNode;
}

export function ChartFrame({
  heightClass = "h-44",
  yTicks,
  xLabels,
  pointCount,
  summary,
  children,
}: ChartFrameProps) {
  return (
    <div>
      <div className="flex">
        <div
          className={`flex w-9 shrink-0 flex-col justify-between pr-1.5 text-right font-mono text-[9px] leading-none text-text-muted ${heightClass}`}
          aria-hidden="true"
        >
          {yTicks.map((tick) => (
            <span key={tick.value}>{tick.label}</span>
          ))}
        </div>

        <div role="img" aria-label={summary} className={`relative min-w-0 flex-1 ${heightClass}`}>
          {yTicks.map((tick) =>
            tick.value <= 0 ? (
              <div
                key={tick.value}
                className="absolute inset-x-0 bottom-0 border-t border-surface-border"
              />
            ) : (
              <div
                key={tick.value}
                className="absolute inset-x-0 border-t border-dashed border-surface-border/70"
                style={{ top: `${(1 - tick.value) * 100}%` }}
              />
            ),
          )}
          <div className="absolute inset-0">{children}</div>
        </div>
      </div>

      <div className="relative ml-9 mt-1 h-3">
        {xLabels.map((label) => {
          const left = xPercent(label.index, pointCount);
          const transform =
            pointCount <= 1
              ? "translateX(-50%)"
              : label.index === 0
                ? "translateX(0)"
                : label.index === pointCount - 1
                  ? "translateX(-100%)"
                  : "translateX(-50%)";
          return (
            <span
              key={`${label.index}-${label.label}`}
              className="absolute top-0 whitespace-nowrap font-mono text-[9px] text-text-muted"
              style={{ left: `${left}%`, transform }}
            >
              {label.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}
