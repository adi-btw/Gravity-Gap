import { expect, test, type Page } from "@playwright/test";
import { blockApi, nav } from "./demo-path";

/** R2 suppression calculator (plan/13-round-2-features.md §R2). Works with the live API or the offline artifacts. */
const ISS = "g=0&p=14.7&o2=0.21&u=10&L=10";
const LUNAR_BASE = "g=1.62&p=8.2&o2=0.34&u=10&L=10";

async function open(page: Page, query: string) {
  await page.goto(`/suppression?${query}`);
  await expect(page.getByRole("heading", { level: 1, name: "Put it out: how dilution affects flames" })).toBeVisible();
  await expect(page.getByTestId("suppression-summary")).toBeVisible({ timeout: 30_000 });
  // Either chip is fine: an API started before /suppression existed 404s it, which falls back to the artifacts.
  await expect(page.getByText(/^(live API|offline data)/).first()).toBeVisible();
}

async function expectSafetyNote(page: Page) {
  const note = page.getByRole("note", { name: "Safety note" });
  await expect(note).toBeVisible();
  await expect(note).toContainText(/dangerous to breathe/);
}

test.describe("suppression calculator", () => {
  test("ISS: a curve with bands and a dose (or 'not reached')", async ({ page }) => {
    await open(page, ISS);
    await expectSafetyNote(page);
    const chart = page.getByTestId("m1-chart");
    await expect(chart).toBeVisible();
    await expect(chart.locator("[data-segment]").first()).toBeVisible();
    await expect(page.getByTestId("suppression-dose")).toHaveText(/(reaches 90%|already ≥90%|not reached inside tested conditions)/);
    await expect(page.getByTestId("suppression-summary")).toContainText("At ISS air (21% O₂)");
    // Table alternative: diluted ISS points inside tested conditions carry numbers.
    await page.getByText("Show M1 as a table").click();
    await expect(page.getByTestId("m1-table").locator('tr[data-applicable="true"]').nth(3)).toBeVisible();
    await expect(page.getByTestId("m2-chart")).toBeVisible();
    await expect(page.getByTestId("tested-dilution-chart")).toBeVisible();
  });

  test("lunar base: no evidence at every diluted point and the O2 ceiling is named", async ({ page }) => {
    await open(page, LUNAR_BASE);
    await expectSafetyNote(page);
    await expect(page.getByTestId("suppression-summary")).toContainText(/no evidence/);
    await expect(page.getByTestId("o2-ceiling")).toContainText(/O₂ ceiling of the dilution tests/);
    await expect(page.getByTestId("suppression-dose")).toHaveText(/not reached inside tested conditions/);
    await page.getByText("Show M1 as a table").click();
    const rows = page.getByTestId("m1-table").locator("tbody tr");
    const n = await rows.count();
    expect(n).toBeGreaterThan(5);
    for (let i = 0; i < n; i++) {
      const row = rows.nth(i);
      if ((await row.getAttribute("data-fraction")) === "0") continue;
      await expect(row).toHaveAttribute("data-applicable", "false");
      await expect(row).toContainText("no evidence");
    }
    await expect(page.getByTestId("m1-chart").locator("[data-gap]").first()).toBeAttached();
    await expect(page.getByText(/above every diluted test/).first()).toBeVisible();
  });

  test("diluent toggle updates the URL and the curve", async ({ page }) => {
    await open(page, ISS);
    const he = page.getByRole("button", { name: /^Helium/ });
    await he.click();
    await expect(page).toHaveURL(/diluent=he/);
    await expect(he).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("m1-chart")).toHaveAttribute("aria-label", /helium/);
    await page.getByRole("button", { name: /^CO₂/ }).click();
    await expect(page).toHaveURL(/diluent=co2/);
  });

  test("offline: the ISS preset works from bundled artifacts; a custom habitat needs the API", async ({ page }) => {
    await blockApi(page);
    await open(page, `${ISS}&diluent=he`);
    await expect(page.getByText("offline data").first()).toBeVisible();
    await expect(page.getByTestId("m1-chart").locator("[data-segment]").first()).toBeVisible();
    await page.getByRole("spinbutton", { name: /Vent speed/ }).fill("7");
    await expect(page.getByText("Live API needed", { exact: true })).toBeVisible();
    await expect(page.getByText(/precomputed suppression curves exist only for the six presets/)).toBeVisible();
  });

  test("reachable from the nav and from /bounds", async ({ page }) => {
    await page.goto(`/bounds?${ISS}`);
    await page.getByRole("link", { name: /How much CO₂ would put it out/ }).click();
    await expect(page).toHaveURL(/\/suppression\?.*o2=0\.21/);
    await expect(nav(page, "Put it out")).toHaveAttribute("aria-current", "page");
  });
});
