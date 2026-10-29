import type { DashboardRange } from "../../api/types";

const RANGES: Array<{ value: DashboardRange; label: string }> = [
  { value: "24h", label: "24h" },
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
];

export function RangeSelector({
  value,
  onChange,
}: {
  value: DashboardRange;
  onChange: (range: DashboardRange) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Date range"
      className="inline-flex items-center rounded-lg border border-surface-border bg-surface-elevated/60 p-0.5"
    >
      {RANGES.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={[
              "rounded-md px-2.5 py-1.5 text-[12px] transition-colors",
              active
                ? "bg-surface-hover font-medium text-text-primary shadow-sm"
                : "text-text-secondary hover:text-text-primary",
            ].join(" ")}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
