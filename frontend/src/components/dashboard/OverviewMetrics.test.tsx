import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { dashboardData } from "../../test/fixtures/dashboard";
import { OverviewMetrics } from "./OverviewMetrics";

describe("OverviewMetrics", () => {
  it("renders the aggregate values and partial-usage note", () => {
    render(<OverviewMetrics overview={dashboardData().overview} />);

    expect(screen.getByText("Conversations")).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.getByText("121")).toBeInTheDocument();
    expect(screen.getByText("138")).toBeInTheDocument();
    expect(screen.getByText("92.8%")).toBeInTheDocument();
    expect(screen.getByText("283.1k")).toBeInTheDocument();
    expect(screen.getByText("83.3k")).toBeInTheDocument();
    expect(screen.getByText("$0.29")).toBeInTheDocument();
    expect(screen.getAllByText("partial · usage missing")).toHaveLength(2);
  });

  it("shows unavailable values rather than invented numbers", () => {
    const overview = dashboardData().overview;
    render(
      <OverviewMetrics
        overview={{
          ...overview,
          attempts: 0,
          success_rate: null,
          input_tokens: null,
          output_tokens: null,
          estimated_cost_usd: null,
          pricing: { ...overview.pricing, available: false },
        }}
      />,
    );

    expect(screen.getAllByText("—")).toHaveLength(3);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText("No terminal attempts")).toBeInTheDocument();
  });
});
