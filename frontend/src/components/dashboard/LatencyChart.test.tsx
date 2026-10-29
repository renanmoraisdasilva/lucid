import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DashboardTrendPoint } from "../../api/types";
import { LatencyChart } from "./LatencyChart";

const points: DashboardTrendPoint[] = [
  {
    bucket_start: "2026-10-27T00:00:00Z",
    attempts: 2,
    completed: 2,
    failed: 0,
    interrupted: 0,
    input_tokens: 10,
    output_tokens: 2,
    ttft_ms_p50: 400,
    ttft_ms_p95: null,
    duration_ms_p50: 2000,
    duration_ms_p95: null,
  },
];

describe("LatencyChart", () => {
  it("shows the period aggregate and explains a thin p95 sample", () => {
    render(
      <LatencyChart
        kind="ttft"
        points={points}
        stats={{ p50_ms: 400, p95_ms: null, samples: 19 }}
        bucket="day"
      />,
    );

    expect(screen.getByText("Time to first token")).toBeInTheDocument();
    expect(screen.getByText("Period median")).toBeInTheDocument();
    expect(screen.getByText("400 ms")).toBeInTheDocument();
    expect(screen.getByText("19 samples")).toBeInTheDocument();
    expect(screen.getByText("p95 needs at least 20 samples.")).toBeInTheDocument();
  });

  it("shows p95 when there are enough samples", () => {
    render(
      <LatencyChart
        kind="duration"
        points={points}
        stats={{ p50_ms: 2000, p95_ms: 9000, samples: 20 }}
        bucket="day"
      />,
    );

    expect(screen.getByText("Generation duration")).toBeInTheDocument();
    expect(screen.getByText("9 s")).toBeInTheDocument();
    expect(screen.queryByText("p95 needs at least 20 samples.")).toBeNull();
  });

  it("explains an empty sample", () => {
    render(
      <LatencyChart
        kind="ttft"
        points={points}
        stats={{ p50_ms: null, p95_ms: null, samples: 0 }}
        bucket="day"
      />,
    );

    expect(screen.getByText("No timed attempts in this range.")).toBeInTheDocument();
  });
});
