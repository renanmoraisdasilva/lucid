import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DashboardEmpty, DashboardError, DashboardLoading, StaleBanner } from "./DashboardStates";

describe("DashboardStates", () => {
  it("[UI-DASH-RULE-001] announces loading without pretending to have data", () => {
    render(<DashboardLoading />);

    const status = screen.getByRole("status", { name: "Loading dashboard" });
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Loading dashboard…")).toBeInTheDocument();
  });

  it("[UI-DASH-RULE-002] explains an empty range", () => {
    render(<DashboardEmpty />);

    expect(screen.getByText("No telemetry in this range")).toBeInTheDocument();
    expect(screen.getByText(/Try a wider range/)).toBeInTheDocument();
  });

  it("[UI-DASH-RULE-003] retries after a request failure", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();

    render(<DashboardError onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/Couldn.t load the dashboard/);
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("keeps stale data visible and retries a refresh", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();

    const { rerender } = render(<StaleBanner onRetry={onRetry} fetching={false} />);

    expect(screen.getByRole("status")).toHaveTextContent(
      /Couldn.t refresh\. Showing the last successful data\./,
    );

    await user.click(screen.getByRole("button", { name: "Retry now" }));
    expect(onRetry).toHaveBeenCalledTimes(1);

    rerender(<StaleBanner onRetry={onRetry} fetching />);
    expect(screen.getByRole("button", { name: "Retry now" })).toBeDisabled();
  });
});
