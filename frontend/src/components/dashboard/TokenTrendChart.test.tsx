import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DashboardTrendPoint } from "../../api/types";
import { TokenTrendChart } from "./TokenTrendChart";

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
    ttft_ms_p95: 800,
    duration_ms_p50: 2000,
    duration_ms_p95: 4000,
  },
  {
    bucket_start: "2026-10-28T00:00:00Z",
    attempts: 1,
    completed: 1,
    failed: 0,
    interrupted: 0,
    input_tokens: null,
    output_tokens: null,
    ttft_ms_p50: null,
    ttft_ms_p95: null,
    duration_ms_p50: null,
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

describe("TokenTrendChart", () => {
  it("renders totals, breaks the line at nulls, and keeps real zeros", () => {
    const { container, getByText } = render(
      <TokenTrendChart points={points} bucket="day" inputTotal={30} outputTotal={6} />,
    );

    expect(getByText("Token usage")).toBeInTheDocument();
    expect(
      getByText("A gap means usage was unavailable; a line at zero is a real zero."),
    ).toBeInTheDocument();
    // Two input segments because the middle bucket has no usage.
    expect(container.querySelectorAll("g.text-amber-accent")).toHaveLength(2);
    expect(getByText("Oct 29")).toBeInTheDocument();
  });
});
