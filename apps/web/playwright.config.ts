import { defineConfig, devices } from "@playwright/test";

// Hermetic hero-flow smoke: the agent endpoints are mocked in the spec, so this
// runs with no live agent and no network. It builds the app and serves it with
// `next start`.
export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "line",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm start",
    url: "http://localhost:3000",
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
  },
});
