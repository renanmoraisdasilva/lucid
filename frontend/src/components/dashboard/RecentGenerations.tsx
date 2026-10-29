import { useCallback, useState } from "react";

import type { DashboardRecentAttempt } from "../../api/types";
import { GenerationDetailsDialog } from "./GenerationDetailsDialog";
import { RecentAttemptCard } from "./RecentAttemptCard";
import { RecentAttemptsTable } from "./RecentAttemptsTable";

export function RecentGenerations({ attempts }: { attempts: DashboardRecentAttempt[] }) {
  const [selected, setSelected] = useState<DashboardRecentAttempt | null>(null);

  const openDetails = useCallback((attempt: DashboardRecentAttempt) => {
    setSelected(attempt);
  }, []);

  const closeDetails = useCallback(() => {
    setSelected(null);
  }, []);

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
            04 / Recent generations
          </span>
          <h2 className="mt-1 text-[15px] font-semibold tracking-tight text-text-primary sm:text-[16px]">
            Latest 25 attempts
          </h2>
        </div>
        <span className="text-[11px] text-text-muted">Select a row for details</span>
      </div>

      {attempts.length === 0 ? (
        <div className="rounded-xl border border-dashed border-surface-border bg-surface-elevated/20 px-4 py-10 text-center">
          <p className="text-[13px] font-medium text-text-primary">No generations in this range</p>
          <p className="mt-1 text-[11px] text-text-secondary">
            Attempts appear here as soon as a generation finishes.
          </p>
        </div>
      ) : (
        <>
          <RecentAttemptsTable attempts={attempts} onSelect={openDetails} />

          <div className="space-y-2.5 xl:hidden">
            {attempts.map((attempt) => (
              <RecentAttemptCard
                key={attempt.attempt_id}
                attempt={attempt}
                onSelect={() => openDetails(attempt)}
              />
            ))}
          </div>

          <p className="text-[11px] text-text-muted">
            Showing {attempts.length} {attempts.length === 1 ? "attempt" : "attempts"} · no
            pagination
          </p>
        </>
      )}

      {selected !== null ? (
        <GenerationDetailsDialog attempt={selected} onClose={closeDetails} />
      ) : null}
    </section>
  );
}
