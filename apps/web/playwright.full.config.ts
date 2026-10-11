import { defineConfig, devices } from "@playwright/test";

// Full-stack tests: the production web build, the real API and Postgres, and the Firebase
// Auth emulator, all started by ./dev/run.sh e2e (locally and in CI). Nothing is stubbed.
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
const launchOptions = executablePath ? { launchOptions: { executablePath } } : {};

export default defineConfig({
  testDir: "./e2e/full",
  // Tests share one database; each signs in as its own made-up users, so they can run in
  // parallel without seeing each other's data.
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: process.env.POPSHOT_E2E_WEB_URL ?? "http://127.0.0.1:3200",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], ...launchOptions } },
    { name: "mobile", use: { ...devices["Pixel 7"], ...launchOptions } },
  ],
});
