import { describe, expect, it } from "vitest";

import {
  axisTicks,
  buildAreaPath,
  buildLinePath,
  buildSegments,
  niceMax,
  selectedIndices,
  seriesMax,
  xPercent,
  yPercent,
} from "./chart";

describe("chart geometry", () => {
  it("rounds axes to readable maxima", () => {
    expect(niceMax(0)).toBe(1);
    expect(niceMax(1120)).toBe(1200);
    expect(niceMax(74800)).toBe(80000);
    expect(axisTicks(1200, 4)).toEqual([0, 300, 600, 900, 1200]);
  });

  it("maps values into percentage space", () => {
    expect(xPercent(0, 7)).toBe(0);
    expect(xPercent(6, 7)).toBe(100);
    expect(xPercent(0, 1)).toBe(50);
    expect(yPercent(600, 1200)).toBe(50);
    expect(yPercent(0, 1200)).toBe(100);
    expect(yPercent(1200, 1200)).toBe(0);
  });

  it("breaks series at nulls", () => {
    const segments = buildSegments([10, null, 20, 30, null], (value) => value);

    expect(segments).toEqual([
      [{ index: 0, value: 10 }],
      [
        { index: 2, value: 20 },
        { index: 3, value: 30 },
      ],
    ]);
  });

  it("builds line and area paths", () => {
    const segment = [
      { index: 0, value: 10 },
      { index: 2, value: 20 },
    ];

    expect(buildLinePath(segment, 3, 20)).toContain("M");
    expect(buildLinePath(segment, 3, 20)).toContain("L");
    expect(buildAreaPath(segment, 3, 20).endsWith("Z")).toBe(true);
  });

  it("keeps single points visible", () => {
    const path = buildLinePath([{ index: 0, value: 10 }], 1, 20);

    expect(path).toContain("L");
  });

  it("selects at most seven labels and always keeps the ends", () => {
    expect(selectedIndices(7)).toEqual([0, 1, 2, 3, 4, 5, 6]);
    expect(selectedIndices(30)).toHaveLength(7);
    expect(selectedIndices(30)[0]).toBe(0);
    expect(selectedIndices(30).at(-1)).toBe(29);
  });

  it("computes a series maximum", () => {
    expect(seriesMax([null, 0])).toBe(1);
    expect(seriesMax([500, 1000])).toBe(1000);
    expect(seriesMax([1120])).toBe(1200);
  });
});
