import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, getDashboard } from "../api/client";
import { dashboardData } from "../test/fixtures/dashboard";
import { DashboardPage } from "./DashboardPage";

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
});

describe("DashboardPage", () => {
  it("loads the default 7-day range and renders the overview", async () => {
    mockedGetDashboard.mockResolvedValue(dashboardData());

    render(<DashboardPage />, { wrapper });

    expect(await screen.findByText("92.8%")).toBeInTheDocument();
    expect(mockedGetDashboard).toHaveBeenCalledWith("7d", expect.any(AbortSignal));
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByText("Last 7 days")).toBeInTheDocument();
    expect(screen.getByText("Token usage")).toBeInTheDocument();
    expect(screen.getByText("Reliability")).toBeInTheDocument();
    expect(screen.getByText("2,097")).toBeInTheDocument();
  });

  it("loads a new range when the selector changes", async () => {
    mockedGetDashboard.mockResolvedValue(dashboardData());
    const user = userEvent.setup();

    render(<DashboardPage />, { wrapper });
    await screen.findByText("92.8%");

    await user.click(screen.getByRole("button", { name: "30 days" }));

    expect(await screen.findByText("Last 30 days")).toBeInTheDocument();
    expect(mockedGetDashboard).toHaveBeenCalledWith("30d", expect.any(AbortSignal));
  });

  it("refreshes manually", async () => {
    mockedGetDashboard.mockResolvedValue(dashboardData());
    const user = userEvent.setup();

    render(<DashboardPage />, { wrapper });
    await screen.findByText("92.8%");

    await user.click(screen.getByRole("button", { name: /Refresh/ }));

    await waitFor(() => expect(mockedGetDashboard).toHaveBeenCalledTimes(2));
    expect(mockedGetDashboard).toHaveBeenLastCalledWith("7d", expect.any(AbortSignal));
  });

  it("keeps the last data and shows a stale banner when a refresh fails", async () => {
    mockedGetDashboard.mockResolvedValueOnce(dashboardData());
    const user = userEvent.setup();

    render(<DashboardPage />, { wrapper });
    await screen.findByText("92.8%");

    mockedGetDashboard.mockRejectedValue(new ApiError("request_failed", "Offline.", 503));
    await user.click(screen.getByRole("button", { name: /Refresh/ }));

    expect(
      await screen.findByText("Couldn't refresh. Showing the last successful data."),
    ).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
  });

  it("shows a full error and can recover when there is no data", async () => {
    mockedGetDashboard.mockRejectedValue(new ApiError("request_failed", "Offline.", 503));
    const user = userEvent.setup();

    render(<DashboardPage />, { wrapper });

    expect(await screen.findByText("Couldn't load the dashboard")).toBeInTheDocument();

    mockedGetDashboard.mockResolvedValue(dashboardData());
    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByText("92.8%")).toBeInTheDocument();
  });
});
