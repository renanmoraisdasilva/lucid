import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DashboardTrendPoint } from "../../api/types";
import { ReliabilityChart } from "./ReliabilityChart";

const points: DashboardTrendPoint[] = [
  {
    bucket_start: "2026-10-28T00:00:00Z",
    attempts: 2,
    completed: 1,
    failed: 1,
    interrupted: 0,
    input_tokens: 10,
    output_tokens: 2,
    ttft_ms_p50: 400,
    ttft_ms_p95: null,
    duration_ms_p50: 2000,
    duration_ms_p95: null,
  },
  {
    bucket_start: "2026-10-29T00:00:00Z",
    attempts: 0,
    completed: 0,
    failed: 0,
    interrupted: 0,
    input_tokens: 0,
    output_tokens: 0,
    ttft_ms_p50: null,
    ttft_ms_p95: null,
    duration_ms_p50: null,
    duration_ms_p95: null,
  },
];

describe("ReliabilityChart", () => {
  it("renders each bucket and explains zero attempts", () => {
    render(<ReliabilityChart points={points} bucket="day" />);

    expect(screen.getByText("Reliability")).toBeInTheDocument();
    expect(screen.getAllByTitle(/completed/)).toHaveLength(2);
    expect(
      screen.getByText("Zero attempts are shown at the baseline, not treated as missing data."),
    ).toBeInTheDocument();
  });
});
