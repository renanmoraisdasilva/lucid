import { describe, expect, it } from "vitest";

import { formatWait } from "./duration";

describe("formatWait", () => {
  it("shows seconds under a minute", () => {
    expect(formatWait(0)).toBe("0s");
    expect(formatWait(30)).toBe("30s");
    expect(formatWait(59)).toBe("59s");
  });

  it("shows minutes and seconds under an hour", () => {
    expect(formatWait(60)).toBe("1m 0s");
    expect(formatWait(125)).toBe("2m 5s");
  });

  it("shows hours and minutes for long quota waits", () => {
    // "retry in 11h2m40s" from the provider's free-tier daily limit.
    expect(formatWait(39760)).toBe("11h 2m");
    expect(formatWait(3600)).toBe("1h 0m");
  });

  it("never renders a negative wait", () => {
    expect(formatWait(-5)).toBe("0s");
  });
});
