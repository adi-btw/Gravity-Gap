import { defineConfig, devices } from "@playwright/test";
import { webServers } from "./playwright.config";

/** H4: records the demo path to docs/media/ (`npm run record-demo`). Not part of `npm run e2e`. */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "record-demo.spec.ts",
  workers: 1,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  reporter: "list",
  outputDir: "test-results/record",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? `http://localhost:${process.env.E2E_WEB_PORT ?? 3000}`,
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    video: { mode: "on", size: { width: 1440, height: 900 } },
    colorScheme: "dark",
  },
  webServer: webServers,
});
