import { describe, expect, it } from "vitest";

import {
  RANGE_LABELS,
  formatCost,
  formatCount,
  formatPercent,
  formatTokens,
  formatUpdated,
} from "./dashboard-format";

describe("dashboard formatting", () => {
  it("formats counts and tokens", () => {
    expect(formatCount(1234)).toBe("1,234");
    expect(formatTokens(0)).toBe("0");
    expect(formatTokens(999)).toBe("999");
    expect(formatTokens(1000)).toBe("1.0k");
    expect(formatTokens(283100)).toBe("283.1k");
    expect(formatTokens(1_500_000)).toBe("1.5M");
    expect(formatTokens(null)).toBe("—");
  });

  it("formats percentages and costs", () => {
    expect(formatPercent(0.9275)).toBe("92.8%");
    expect(formatPercent(null)).toBe("—");
    expect(formatCost(0.29)).toBe("$0.29");
    expect(formatCost(null)).toBe("Unavailable");
  });

  it("describes the last successful refresh", () => {
    const now = Date.UTC(2026, 9, 29, 15, 30, 0);

    expect(formatUpdated(0, now)).toBe("Not loaded yet");
    expect(formatUpdated(now - 2_000, now)).toBe("Updated just now");
    expect(formatUpdated(now - 42_000, now)).toBe("Updated 42s ago");
    expect(formatUpdated(now - 5 * 60_000, now)).toBe("Updated 5m ago");
    expect(formatUpdated(now - 2 * 60 * 60_000, now)).toBe("Updated 2h ago");
  });

  it("labels the ranges", () => {
    expect(RANGE_LABELS["24h"]).toBe("Last 24 hours");
    expect(RANGE_LABELS["7d"]).toBe("Last 7 days");
    expect(RANGE_LABELS["30d"]).toBe("Last 30 days");
  });
});
