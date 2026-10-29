import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getDashboard } from "../api/client";
import { dashboardData } from "../test/fixtures/dashboard";
import { useDashboard } from "./useDashboard";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, getDashboard: vi.fn() };
});

const mockedGetDashboard = vi.mocked(getDashboard);
let client: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  client = new QueryClient({
    defaultOptions: { queries: { retryDelay: 0, refetchOnWindowFocus: false } },
  });
  mockedGetDashboard.mockReset();
});

afterEach(() => {
  client.clear();
  vi.useRealTimers();
});

describe("useDashboard", () => {
  it("refetches every 20 seconds", async () => {
    vi.useFakeTimers();
    mockedGetDashboard.mockResolvedValue(dashboardData());

    const { unmount } = renderHook(() => useDashboard("7d"), { wrapper });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(mockedGetDashboard).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });
    expect(mockedGetDashboard).toHaveBeenCalledTimes(2);

    unmount();
  });
});
