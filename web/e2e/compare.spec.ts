import { expect, test, type Page } from "@playwright/test";
import { blockApi, nav } from "./demo-path";

/** S4 side-by-side habitat compare (plan/15-round-3-features.md §S4). Works with the live API or the offline artifacts. */
const ISS = "g=0&p=14.7&o2=0.21&u=10&L=10";
const LUNAR_BASE = "g=1.62&p=8.2&o2=0.34&u=10&L=10";

async function open(page: Page, query: string) {
  await page.goto(`/compare?${query}`);
  await expect(page.getByRole("heading", { level: 1, name: "Compare two habitats side by side" })).toBeVisible();
  await expect(page.getByTestId("compare-summary")).toBeVisible({ timeout: 30_000 });
  // Either chip is fine: an API started before /compare existed 404s it, which falls back to the bounds artifacts.
  await expect(page.getByText(/^(live API|offline data)/).first()).toBeVisible();
}

test.describe("habitat compare", () => {
  test("ISS vs lunar base: M2 'no evidence' on the right only, no difference shown", async ({ page }) => {
    await open(page, `a=iss&b=lunar_base&${LUNAR_BASE}`);
    const summary = page.getByTestId("compare-summary");
    await expect(summary).toContainText("Moving from ISS to Lunar base changes gravity");
    await expect(summary).toContainText("M2, M4 and M5 lose their evidence at Lunar base");
    await expect(page.getByTestId("side-a-M2")).toHaveAttribute("data-applicable", "true");
    await expect(page.getByTestId("side-b-M2")).toHaveAttribute("data-applicable", "false");
    await expect(page.getByTestId("side-b-M2")).toContainText("No evidence");
    await expect(page.getByTestId("side-a-M2")).not.toContainText("No evidence");
    await expect(page.getByTestId("compare-diff-M2")).toContainText("No difference shown: Lunar base has no evidence for M2.");
    // Both covered: one shared axis with both habitats, and a real difference line.
    await expect(page.getByTestId("side-b-M1")).toHaveAttribute("data-applicable", "true");
    await expect(page.getByTestId("compare-diff-M1")).toContainText("Lower at Lunar base");
    await expect(page.getByTestId("compare-row-M1").getByRole("group", { name: /M1 on one shared axis: ISS: .*Lunar base: / })).toBeVisible();
    await expect(page.getByTestId("compare-row-M1")).toContainText("regime: mixed");
  });

  test("pickers and swap keep both habitats in the URL", async ({ page }) => {
    await open(page, `a=iss&b=lunar_base&${LUNAR_BASE}`);
    await page.getByLabel("Habitat A").selectOption("mars_base");
    await expect(page).toHaveURL(/a=mars_base/);
    await expect(page).toHaveURL(/b=lunar_base/);
    await expect(page.getByTestId("compare-summary")).toContainText("Moving from Mars base to Lunar base");
    await page.getByRole("button", { name: "Swap A and B" }).click();
    await expect(page).toHaveURL(/a=lunar_base.*b=mars_base/);
    await expect(page.getByTestId("compare-summary")).toContainText("Moving from Lunar base to Mars base");
    await page.reload();
    await expect(page.getByLabel("Habitat A")).toHaveValue("lunar_base");
    await expect(page.getByLabel("Habitat B")).toHaveValue("mars_base");
  });

  test("offline: preset pair from bundled bounds; a custom habitat needs the API", async ({ page }) => {
    await blockApi(page);
    await open(page, `a=iss&b=current&${LUNAR_BASE}`);
    await expect(page.getByText("offline data").first()).toBeVisible();
    await expect(page.getByTestId("side-b-M2")).toHaveAttribute("data-applicable", "false");
    await page.getByRole("spinbutton", { name: /Vent speed/ }).fill("7");
    await expect(page.getByText("Live API needed", { exact: true })).toBeVisible();
    await expect(page.getByText(/Live API needed to compare a custom habitat/)).toBeVisible();
    await expect(page.getByTestId("compare-summary")).toHaveCount(0);
  });

  test("reachable from the nav and from /bounds ('Compare with…')", async ({ page }) => {
    await page.goto(`/bounds?${LUNAR_BASE}`);
    await page.getByRole("link", { name: /Compare with…/ }).click();
    await expect(page).toHaveURL(/\/compare\?.*a=current.*b=iss/);
    await expect(nav(page, "Compare")).toHaveAttribute("aria-current", "page");
    await expect(page.getByTestId("compare-summary")).toContainText("Moving from Lunar base to ISS", { timeout: 30_000 });
  });

  test("phone: the two sides stack", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await open(page, `a=iss&b=lunar_base&${ISS}`);
    const a = await page.getByTestId("side-a-M1").boundingBox();
    const b = await page.getByTestId("side-b-M1").boundingBox();
    expect(a && b && b.y > a.y + a.height - 1).toBeTruthy();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
