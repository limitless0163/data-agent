import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const root = path.resolve(__dirname, "..");
export default defineConfig({
  testDir: "../tests/e2e",
  testMatch: "*.spec.ts",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 2,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  outputDir: "test-results",
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uv run --project backend --frozen python -m uvicorn backend_app:app --app-dir tests/e2e --host 127.0.0.1 --port 8100",
      cwd: root,
      url: "http://127.0.0.1:8100/openapi.json",
      reuseExistingServer: false,
      timeout: 60_000,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
      cwd: path.join(root, "frontend"),
      url: "http://127.0.0.1:3100",
      env: { API_BASE_URL: "http://127.0.0.1:8100", NEXT_TELEMETRY_DISABLED: "1" },
      reuseExistingServer: false,
      timeout: 90_000,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
    },
  ],
});
