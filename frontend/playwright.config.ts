import { defineConfig, devices } from "@playwright/test";

/**
 * Browser end-to-end suite.
 *
 * Expects a running stack. For a deterministic run, start it with the fake
 * provider (`docker compose -f docker-compose.yml -f docker-compose.e2e.yml
 * --profile full up -d --build`) or set E2E_BASE_URL.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:8080",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
});
