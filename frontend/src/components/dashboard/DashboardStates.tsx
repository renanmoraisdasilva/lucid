export function DashboardLoading() {
  return (
    <div aria-label="Loading dashboard" className="space-y-3">
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4 xl:grid-cols-7">
        {Array.from({ length: 7 }, (_, index) => (
          <div
            key={index}
            className="h-[86px] animate-pulse rounded-xl border border-surface-border bg-surface-elevated/40"
          />
        ))}
      </div>
      <div className="h-52 animate-pulse rounded-xl border border-surface-border bg-surface-elevated/30" />
    </div>
  );
}

export function DashboardError({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-danger-border bg-danger-dim px-6 py-10 text-center"
    >
      <h2 className="text-[15px] font-semibold text-text-primary">
        Couldn&apos;t load the dashboard
      </h2>
      <p className="mx-auto mt-1.5 max-w-md text-[12px] leading-relaxed text-text-secondary">
        The request failed before any data arrived. Nothing is shown rather than zeroed values.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-surface-border-subtle bg-surface-elevated px-3 py-1.5 text-[12px] font-medium text-text-primary transition-colors hover:bg-surface-hover"
      >
        Retry
      </button>
    </div>
  );
}

export function StaleBanner({ onRetry, fetching }: { onRetry: () => void; fetching: boolean }) {
  return (
    <div
      role="status"
      className="flex flex-col gap-2 rounded-lg border border-amber-border bg-amber-dim px-3.5 py-2.5 sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <p className="text-[12px] font-medium text-text-primary">
          Couldn&apos;t refresh. Showing the last successful data.
        </p>
        <p className="mt-0.5 text-[11px] text-text-secondary">
          Automatic refresh keeps trying every 20 seconds.
        </p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        disabled={fetching}
        className="self-start rounded-md border border-amber-border px-2.5 py-1 text-[11px] font-medium text-amber-accent transition-colors hover:bg-amber-accent/10 disabled:opacity-50 sm:self-auto"
      >
        Retry now
      </button>
    </div>
  );
}
