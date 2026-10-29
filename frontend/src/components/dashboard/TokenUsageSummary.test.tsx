import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { dashboardData } from "../../test/fixtures/dashboard";
import { TokenUsageSummary } from "./TokenUsageSummary";

describe("TokenUsageSummary", () => {
  it("renders totals and averages with the partial-usage note", () => {
    render(<TokenUsageSummary overview={dashboardData().overview} />);

    expect(screen.getByText("283.1k")).toBeInTheDocument();
    expect(screen.getByText("83.3k")).toBeInTheDocument();
    expect(screen.getByText("2,097")).toBeInTheDocument();
    expect(screen.getByText("617")).toBeInTheDocument();
    expect(screen.getAllByText("partial · usage missing")).toHaveLength(2);
  });

  it("shows averages as unavailable when no usage was reported", () => {
    const overview = dashboardData().overview;

    render(
      <TokenUsageSummary
        overview={{
          ...overview,
          input_tokens: null,
          output_tokens: null,
          average_input_tokens: null,
          average_output_tokens: null,
          usage_partial: true,
        }}
      />,
    );

    expect(screen.getAllByText("—")).toHaveLength(4);
  });
});
