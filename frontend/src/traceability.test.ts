import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..", "..");
const cli = resolve(repoRoot, "..", "..", "trace-docs", "dist", "cli", "index.js");

describe("traceability", () => {
  it("documentation and tests move together", () => {
    expect(() =>
      execFileSync(process.execPath, [cli, "--root", repoRoot, "verify"], {
        stdio: "pipe",
      }),
    ).not.toThrow();
  }, 30_000);
});
