import { defineConfig, devices } from "@playwright/test";

// Smoke tests against a production build (`next start`) and a stub API that echoes
// what it received, so we can see exactly what the web layer forwards.
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure" },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        ...(executablePath ? { launchOptions: { executablePath } } : {}),
      },
    },
    {
      name: "mobile",
      use: {
        ...devices["Pixel 7"],
        ...(executablePath ? { launchOptions: { executablePath } } : {}),
      },
    },
  ],
  webServer: [
    {
      command: "node e2e/stub-api.mjs",
      url: "http://127.0.0.1:4010/healthz",
      reuseExistingServer: false,
    },
    {
      // Run the standalone server exactly as the container will.
      command:
        "rm -rf .next/standalone/.next/static && cp -r .next/static .next/standalone/.next/static && node .next/standalone/server.js",
      url: "http://127.0.0.1:3100/icons/192",
      reuseExistingServer: false,
      env: {
        HOSTNAME: "127.0.0.1",
        PORT: "3100",
        API_BASE_URL: "http://127.0.0.1:4010",
        FIREBASE_API_KEY: "test-api-key-not-real",
        FIREBASE_AUTH_DOMAIN: "popshot-test.firebaseapp.com",
        FIREBASE_PROJECT_ID: "popshot-test",
        FIREBASE_APP_ID: "1:000000000000:web:0000000000000000",
      },
    },
  ],
});
