import { expect, test, type Page } from "@playwright/test";
import { blockApi, nav } from "./demo-path";

/** R3 detection evidence (plan/contracts.md R3 addendum, ADR-0007). Works with the live API or the bundled artifact. */
async function open(page: Page, query = "") {
  await page.goto(`/detection${query}`);
  await expect(page.getByRole("heading", { level: 1, name: "Detection evidence" })).toBeVisible();
  await expect(page.getByTestId("bins-chart")).toBeVisible({ timeout: 30_000 });
  // Either chip is fine: an API started before /detection existed 404s it, which falls back to the artifact.
  await expect(page.getByText(/^(live API|offline data)/).first()).toBeVisible();
}

test.describe("detection evidence", () => {
  test("renders the scope note, the lunar dust gap and every chart with a source", async ({ page }) => {
    await open(page);
    await expect(page.getByTestId("scope-note")).toContainText(/Reduced scope/);
    const lunar = page.getByRole("note", { name: /could lunar dust fool a smoke detector/ });
    await expect(lunar).toBeVisible();
    await expect(page.getByTestId("gap-lunar_dust")).toContainText(/Arizona Road Dust/);
    await expect(page.getByTestId("gaps-list").getByRole("listitem")).toHaveCount(9);
    for (const id of ["bins-chart", "runs-chart", "amc-chart", "sim-chart-1", "sim-chart-2"]) {
      const chart = page.getByTestId(id);
      await expect(chart).toBeVisible();
      await expect(chart).toHaveAttribute("aria-label", /nanometres on a log scale/);
      await expect(chart).toHaveAttribute("aria-label", /PSI-\d+/);
    }
    expect(await page.getByTestId("source-line").count()).toBeGreaterThanOrEqual(7);
    await expect(page.getByTestId("bins-stats")).toContainText("Particles counted");
  });

  test("material picker and particle toggle change the size distribution chart", async ({ page }) => {
    await open(page);
    const chart = page.getByTestId("bins-chart");
    await expect(chart).toHaveAttribute("aria-label", /Cotton lamp wick/);
    const before = await chart.locator("polyline").getAttribute("points");
    const silicone = page.getByRole("button", { name: "Silicone", exact: true });
    await silicone.click();
    await expect(silicone).toHaveAttribute("aria-pressed", "true");
    await expect(page).toHaveURL(/material=Silicone/);
    await expect(chart).toHaveAttribute("aria-label", /^Silicone smoke, run 60: all particles/);
    expect(await chart.locator("polyline").getAttribute("points")).not.toBe(before);
    await expect(page.getByTestId("source-line").first()).toContainText(/silicone/i);
    await page.getByRole("button", { name: /Larger particles only/ }).click();
    await expect(chart).toHaveAttribute("aria-label", /^Silicone smoke, run 60: larger particles only/);
    await page.getByRole("button", { name: "Kapton", exact: true }).click();
    await expect(page.getByTestId("bins-title")).toHaveText(/^Kapton smoke, run 62: larger particles only/);
  });

  test("dust is Arizona Road Dust with the density note; no series label says lunar", async ({ page }) => {
    await open(page);
    const amc = page.getByTestId("amc-chart");
    await expect(amc.locator("[data-series-label]").filter({ hasText: "Arizona Road Dust (DAFT)" })).toHaveCount(1);
    await expect(amc).toContainText(/assumes density 1 g\/cm³/);
    await expect(page.getByTestId("density-note")).toBeVisible();
    await expect(page.getByTestId("density-note")).toContainText(/density of 1 g\/cm3/);
    await page.getByRole("button", { name: /model checks/ }).click();
    const labels = await page.locator("[data-series-label]").allTextContents();
    expect(labels.length).toBeGreaterThan(10);
    for (const l of labels) expect(l).not.toMatch(/lunar/i);
    for (const id of ["bins-chart", "runs-chart", "amc-chart", "sim-chart-1", "sim-chart-2"]) {
      expect(await page.getByTestId(id).getAttribute("aria-label")).not.toMatch(/lunar/i);
    }
  });

  test("simulation is labelled, shows the share above 20 µm and hides variants until asked", async ({ page }) => {
    await open(page);
    await expect(page.getByText("Simulation", { exact: true })).toBeVisible();
    const case1 = page.getByTestId("sim-case-1");
    await expect(case1.locator("[data-series-label]")).toHaveCount(2);
    await expect(case1.locator("[data-series-label]").first()).toContainText("(simulation, dibutyl phthalate surrogate, t = 7 s)");
    await expect(page.getByTestId("share20-psi115_case1_earth")).toHaveText(/%$/);
    await page.getByRole("button", { name: /model checks/ }).click();
    await expect(case1.locator("[data-series-label]")).toHaveCount(4);
    await expect(page.getByTestId("sim-case-2").locator("[data-series-label]")).toHaveCount(2);
  });

  test("offline: renders from the bundled artifact", async ({ page }) => {
    await blockApi(page);
    await open(page);
    await expect(page.getByText("offline data").first()).toBeVisible();
    await expect(page.getByTestId("runs-chart").locator("[data-row]")).toHaveCount(5);
  });

  test("reachable from the nav and from the Artemis II card on /replay", async ({ page }) => {
    await page.goto("/replay");
    await page.getByTestId("incident-artemis2").getByTestId("detection-link").click();
    await expect(page).toHaveURL(/\/detection/);
    await expect(nav(page, "Detection")).toHaveAttribute("aria-current", "page");
  });

  test("mobile width: no horizontal page scroll", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await open(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
