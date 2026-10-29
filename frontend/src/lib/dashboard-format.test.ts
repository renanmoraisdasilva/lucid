import { describe, expect, it } from "vitest";

import {
  RANGE_LABELS,
  bucketLabel,
  formatAxisMs,
  formatCompactNumber,
  formatCost,
  formatCount,
  formatMs,
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

  it("formats milliseconds and axis labels", () => {
    expect(formatMs(null)).toBe("—");
    expect(formatMs(486)).toBe("486 ms");
    expect(formatMs(1000)).toBe("1 s");
    expect(formatMs(1040)).toBe("1.04 s");
    expect(formatMs(5700)).toBe("5.7 s");
    expect(formatAxisMs(0)).toBe("0");
    expect(formatAxisMs(300)).toBe("300");
    expect(formatAxisMs(1000)).toBe("1s");
    expect(formatAxisMs(1200)).toBe("1.2s");
  });

  it("formats compact axis numbers", () => {
    expect(formatCompactNumber(0)).toBe("0");
    expect(formatCompactNumber(750)).toBe("750");
    expect(formatCompactNumber(1500)).toBe("1.5k");
    expect(formatCompactNumber(80000)).toBe("80k");
    expect(formatCompactNumber(1_000_000)).toBe("1M");
  });

  it("formats UTC bucket labels", () => {
    expect(bucketLabel("2026-10-29T00:00:00Z", "day")).toBe("Oct 29");
    expect(bucketLabel("2026-10-29T15:00:00Z", "hour")).toBe("15:00");
    expect(bucketLabel("2026-10-29T00:00:00Z", "hour")).toBe("00:00");
  });
});
