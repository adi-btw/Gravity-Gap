import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * T7 (E2E demo path, online and offline) and T8 (axe accessibility) — plan/08-testing-qa.md.
 *
 * `npm run e2e` starts both servers unless they are already running locally:
 *  - the FastAPI backend from the repo root on :8000
 *  - the production web build on :3000 (set E2E_NO_BUILD=1 to reuse an existing `.next` build)
 *
 * The demo recording (record-demo.spec.ts) is excluded here; it has its own playwright.record.config.ts.
 */
const PORT = Number(process.env.E2E_WEB_PORT ?? 3000);
const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`;
// Playwright stops webServer processes on Windows with `taskkill /T /F`. Some shells (sandboxes, Git Bash
// profiles) drop System32 from PATH, so the kill silently fails and the run never exits: put it back.
if (process.platform === "win32") {
  const sys32 = path.join(process.env.SystemRoot ?? "C:/Windows", "System32");
  const parts = (process.env.PATH ?? "").split(path.delimiter);
  if (!parts.some((p) => p.toLowerCase() === sys32.toLowerCase())) process.env.PATH = [...parts, sys32].join(path.delimiter);
}

// `next start` runs through node directly, so the process tree is one level shallower than `npm run start`.
const startCommand = `node node_modules/next/dist/bin/next start -p ${PORT}`;
const webCommand = process.env.E2E_NO_BUILD ? startCommand : `npm run build && ${startCommand}`;

export const webServers = [
  {
    command: "python -m uvicorn api.main:app --port 8000",
    cwd: "..",
    url: "http://127.0.0.1:8000/health",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    stdout: "ignore" as const,
    stderr: "pipe" as const,
  },
  {
    command: webCommand,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 300_000,
    stdout: "ignore" as const,
    stderr: "pipe" as const,
  },
];

export default defineConfig({
  testDir: "./e2e",
  testIgnore: ["**/record-demo.spec.ts"],
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: BASE_URL,
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: webServers,
});
