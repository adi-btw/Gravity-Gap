import { expect, test } from "@playwright/test";
import { boundsM1, pickLunarBase, runDemoPath, warmApi } from "./demo-path";

test.beforeAll(async ({ request }) => {
  await warmApi(request);
});

/** T7 online: the scripted judge path against the live API, in under 2 minutes. */
test("judge demo path (lunar base, live API) completes in under 120 s", async ({ page }) => {
  const t0 = Date.now();
  await runDemoPath(page);
  const seconds = (Date.now() - t0) / 1000;
  test.info().annotations.push({ type: "demo-path-seconds", description: seconds.toFixed(1) });
  console.log(`demo path: ${seconds.toFixed(1)} s`);
  expect(seconds).toBeLessThan(120);
});

test("live API chips show on the API-backed pages", async ({ page }) => {
  await page.goto("/");
  await pickLunarBase(page);
  await boundsM1(page);
  await expect(page.getByText("live API").first()).toBeVisible();
  await expect(page.getByText("offline data")).toHaveCount(0);
});
