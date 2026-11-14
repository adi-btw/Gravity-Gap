import { expect, test } from "@playwright/test";
import {
  blockApi,
  boundsM1,
  boundsM2,
  gotoViaNav,
  landing,
  ledger,
  pickLunarBase,
  planner,
  pressureGravity,
  regimeMixed,
} from "./demo-path";

const LUNAR_BASE = "g=1.62&p=8.2&o2=0.34&u=10&L=10";

/** T7 offline: the API is unreachable (every request to :8000 is aborted); the demo must still run. */
test.describe("offline mode (API blocked)", () => {
  test.beforeEach(async ({ page }) => {
    await blockApi(page);
  });

  test("key demo steps run from bundled artifacts with offline chips", async ({ page }) => {
    const t0 = Date.now();
    await landing(page);
    await pickLunarBase(page);
    await regimeMixed(page);
    await pressureGravity(page);
    await boundsM1(page);
    await expect(page.getByText("offline data").first()).toBeVisible();
    await boundsM2(page);
    await expect(page.getByText("offline data").first()).toBeVisible();

    // Explain on M1 asks a pre-generated question, so the offline cache answers it.
    await page.getByRole("button", { name: /^M1/ }).click();
    const section = page.getByRole("region", { name: "Explain this prediction" });
    await section.getByRole("button", { name: "Explain", exact: true }).click();
    await expect(section.getByText(/mode: cached answer/)).toBeVisible();
    await expect(section.getByText("offline data").first()).toBeVisible();

    await ledger(page);
    await expect(page.getByText("offline data").first()).toBeVisible();
    await planner(page);
    await expect(page.getByText("offline data").first()).toBeVisible();
    expect((Date.now() - t0) / 1000).toBeLessThan(120);
  });

  test("a custom habitat says the live API is needed for bounds", async ({ page }) => {
    await page.goto(`/bounds?${LUNAR_BASE}&metric=M1`);
    await expect(page.getByTestId("bounds-estimate")).toBeVisible();
    const vent = page.getByRole("spinbutton", { name: /Vent speed/ });
    await vent.fill("7");
    await expect(page.getByText("Custom", { exact: true })).toBeVisible();
    await expect(page.getByText("Live API needed", { exact: true })).toBeVisible();
    await expect(page.getByText(/custom habitats/)).toBeVisible();
    await expect(page.getByTestId("bounds-estimate")).toHaveCount(0);
  });

  test("the data explorer says the live API is needed", async ({ page }) => {
    await page.goto(`/data?${LUNAR_BASE}`);
    await expect(page.getByText("Live API needed", { exact: true })).toBeVisible();
  });

  test("Ask answers a cached demo question offline and refuses others", async ({ page }) => {
    await page.goto(`/regime?${LUNAR_BASE}`);
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Ask Gravity Gap" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Why is the lunar base in the mixed regime?" }).click();
    await dialog.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(dialog.getByText(/mode: cached answer/)).toBeVisible();
    await expect(dialog.getByText("offline data").first()).toBeVisible();
    await expect(dialog.getByRole("heading", { name: "Citations" })).toBeVisible();

    await dialog.getByRole("textbox", { name: "Your question" }).fill("Explain quantum gravity to me");
    await dialog.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(dialog.getByText(/live API is needed/)).toBeVisible();
  });

  test("explore falls back to catalog order", async ({ page }) => {
    await page.goto(`/explore?${LUNAR_BASE}`);
    await expect(page.getByText("offline data").first()).toBeVisible();
    await gotoViaNav(page, "About", /\/about\?/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
});
