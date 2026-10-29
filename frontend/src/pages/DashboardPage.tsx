import { useState } from "react";

import type { DashboardRange } from "../api/types";
import { DashboardToolbar } from "../components/dashboard/DashboardToolbar";
import {
  DashboardError,
  DashboardLoading,
  StaleBanner,
} from "../components/dashboard/DashboardStates";
import { OverviewMetrics } from "../components/dashboard/OverviewMetrics";
import { TokenUsageSummary } from "../components/dashboard/TokenUsageSummary";
import { TrendsSection } from "../components/dashboard/TrendsSection";
import { useDashboard } from "../hooks/useDashboard";

export function DashboardPage() {
  const [range, setRange] = useState<DashboardRange>("7d");
  const dashboard = useDashboard(range);
  const data = dashboard.data;
  const refresh = () => void dashboard.refetch();

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-14 shrink-0 items-center border-b border-surface-border px-4 sm:px-6">
        <h1 className="text-[14px] font-medium">Dashboard</h1>
      </header>

      <main className="flex-1 overflow-y-auto px-4 py-5 sm:px-6 md:px-8">
        <div className="mx-auto w-full max-w-6xl space-y-5">
          <DashboardToolbar
            range={range}
            onRangeChange={setRange}
            updatedAt={dashboard.dataUpdatedAt}
            fetching={dashboard.isFetching}
            onRefresh={refresh}
          />

          {dashboard.error !== null && data !== undefined ? (
            <StaleBanner onRetry={refresh} fetching={dashboard.isFetching} />
          ) : null}

          {dashboard.isPending ? <DashboardLoading /> : null}

          {dashboard.error !== null && data === undefined ? (
            <DashboardError onRetry={refresh} />
          ) : null}

          {data !== undefined ? (
            <>
              <OverviewMetrics overview={data.overview} />
              <TrendsSection
                trend={data.trend}
                latency={data.latency}
                bucket={data.bucket}
                inputTotal={data.overview.input_tokens}
                outputTotal={data.overview.output_tokens}
              />
              <TokenUsageSummary overview={data.overview} />
            </>
          ) : null}
        </div>
      </main>
    </div>
  );
}
