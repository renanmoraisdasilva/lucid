import { useQuery } from "@tanstack/react-query";

import { getDashboard } from "../api/client";
import type { DashboardRange } from "../api/types";
import { DASHBOARD_REFRESH_MS } from "../lib/dashboard-format";

/**
 * Dashboard data for one range.
 *
 * The range is part of the query key, so switching ranges starts a fresh load
 * instead of showing the previous range's numbers under a new label. Automatic
 * refetching pauses while the tab is in the background.
 */
export function useDashboard(range: DashboardRange) {
  return useQuery({
    queryKey: ["dashboard", range],
    queryFn: ({ signal }) => getDashboard(range, signal),
    refetchInterval: DASHBOARD_REFRESH_MS,
    refetchIntervalInBackground: false,
    retry: 1,
    staleTime: 0,
  });
}
