import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";

const webDir = __dirname;
const brandPortalDir = resolve(__dirname, "../brand-portal");

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "./test-results",
  fullyParallel: true,
  timeout: 90_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: "http://127.0.0.1:3200",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `npm --prefix ${webDir} run build && npm --prefix ${webDir} run start -- --hostname 127.0.0.1 --port 3200`,
      url: "http://127.0.0.1:3200",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        NEXT_PUBLIC_API_URL: "http://127.0.0.1:18000/api/v1",
      },
    },
    {
      command: `npm --prefix ${brandPortalDir} run build && npm --prefix ${brandPortalDir} run preview -- --host 127.0.0.1 --port 3201`,
      url: "http://127.0.0.1:3201",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        VITE_API_URL: "http://127.0.0.1:18000/api/v1",
      },
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
