import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { API_URL, blockApi, nav } from "./demo-path";

/**
 * S2 "Can I trust it?" (/trust, ADR-0009) and the S3 band-width breakdown on /bounds (ADR-0008).
 * Works with the live API or the bundled artifacts: an API started before /holdout or the `drivers` field existed
 * falls back to artifacts/holdout.json and artifacts/uncertainty/{preset}.json.
 */
const LUNAR_BASE = "g=1.62&p=8.2&o2=0.34&u=10&L=10";
const HOLDOUT = JSON.parse(readFileSync(path.resolve(__dirname, "../../artifacts/holdout.json"), "utf-8"));
const SHOTS = process.env.E2E_SHOTS_DIR;

async function openTrust(page: Page, query = "") {
  await page.goto(`/trust${query ? `?${query}` : ""}`);
  await expect(page.getByRole("heading", { level: 1, name: "Can I trust it?" })).toBeVisible();
  await expect(page.getByTestId("score-overall")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/^(live API|offline data)/).first()).toBeVisible();
}

test.describe("/trust honesty test", () => {
  test("scorecard shows the lenient rate with the strict rate, pooled checks, gate check and SAFFIRE caveat", async ({ page }) => {
    await openTrust(page);
    const ov = HOLDOUT.overall.band_coverage;
    await expect(page.getByTestId("coverage-overall")).toContainText(`${ov.k} of ${ov.n}`);
    for (const m of ["M1", "M3"]) {
      const s = HOLDOUT.metrics[m].summary.strict_coverage;
      await expect(page.getByTestId(`strict-${m}`)).toContainText(`${s.k} of ${s.n}`);
      await expect(page.getByTestId(`score-${m}`)).toContainText("Pooled Brier score");
    }
    const m2 = HOLDOUT.metrics.M2.summary.tests_inside_band_covered;
    await expect(page.getByTestId("score-M2")).toContainText(`${m2.k} of ${m2.n}`);
    await expect(page.getByTestId("score-M2")).toContainText("under the nominal 90%");
    // Gate check from the wide check, never from the primary test.
    const nej = HOLDOUT.wide_check.overall.no_evidence_justified;
    await expect(page.getByTestId("score-gate")).toContainText(`${nej.n} groups got “no evidence”`);
    await expect(page.getByTestId("score-gate")).toContainText(`For ${nej.k} of them`);
    // Weak test wherever weak_test is true (wide-check M3), and the skipped groups with their reason.
    await expect(page.getByTestId("wide-M3").getByTestId("weak-test")).toBeVisible();
    await expect(page.getByTestId("wide-M3")).toContainText(`${HOLDOUT.wide_check.metrics.M3.summary.n_skipped} skipped`);
    await expect(page.getByTestId("skip-reason-M3")).toContainText("too few remaining tests");
    // SAFFIRE 7/9 with its caveat next to it.
    const sf = HOLDOUT.saffire_hindcast.headline;
    await expect(page.getByTestId("score-saffire")).toContainText(`${sf.hits} of ${sf.n}`);
    await expect(page.getByTestId("saffire-caveat")).toContainText("Not discriminative");
    await expect(page.getByTestId("hit-rules").getByRole("listitem")).toHaveCount(3);
    if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "trust.png"), fullPage: true });
  });

  test("map uses shapes for hit / miss / no evidence and the misses table names PSI rows", async ({ page }) => {
    await openTrust(page);
    const map = page.getByTestId("holdout-map");
    await expect(map).toHaveAttribute("aria-label", /band held \(filled circles\).*band missed \(hollow circles with a cross\)/);
    const misses = HOLDOUT.metrics.M1.groups.filter((g: { hit: boolean }) => g.hit === false).length;
    await expect(map.locator('[data-mark="miss"]')).toHaveCount(misses);
    await expect(map.locator('[data-mark="miss"] path')).toHaveCount(misses); // the cross
    const rows = page.getByTestId("miss-row");
    const n = ["M1", "M2", "M3"].reduce((s, m) => s + HOLDOUT.metrics[m].summary.worst_misses.length, 0);
    await expect(rows).toHaveCount(n);
    await expect(rows.first().getByTestId("psi-rows")).toContainText(/PSI-69:FLEX:\d+/);

    // Wide check, M3: grey squares for "no evidence", dashed rings for skipped, all counted.
    await page.getByRole("button", { name: "M3", exact: true }).click();
    await page.getByRole("button", { name: "Wide check" }).click();
    await expect(page).toHaveURL(/scheme=wide/);
    const w = HOLDOUT.wide_check.metrics.M3.summary;
    await expect(map.locator('[data-grey="no_evidence"]')).toHaveCount(w.n_not_covered);
    await expect(map.locator('[data-grey="skipped"]')).toHaveCount(w.n_skipped);
    await expect(page.getByTestId("map-skipped")).toContainText(`${w.n_skipped} groups: too few remaining tests`);
    await expect(page.getByRole("heading", { name: /Worst misses \(wide check\)/ })).toBeVisible();
  });

  test("offline: renders from the bundled artifact", async ({ page }) => {
    await blockApi(page);
    await openTrust(page);
    await expect(page.getByText("offline data").first()).toBeVisible();
    await expect(page.getByTestId("coverage-overall")).toContainText(`${HOLDOUT.overall.band_coverage.k} of`);
  });

  test("reachable from the nav, /about and the Bounds panel", async ({ page }) => {
    await page.goto(`/bounds?${LUNAR_BASE}`);
    await page.getByTestId("trust-link").click();
    await expect(page).toHaveURL(/\/trust/);
    await expect(nav(page, "Trust")).toHaveAttribute("aria-current", "page");
    await page.goto("/about");
    await page.getByRole("link", { name: "Can I trust it? page" }).click();
    await expect(page).toHaveURL(/\/trust/);
  });

  test("mobile width: no horizontal page scroll", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await openTrust(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test.describe("/bounds band-width breakdown", () => {
  test("lunar base M1 shows the stacked bar with shares and basis; tornado is behind a disclosure", async ({ page }) => {
    await page.goto(`/bounds?${LUNAR_BASE}&metric=M1`);
    const drivers = page.getByTestId("drivers");
    await expect(drivers).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("drivers-bar")).toHaveAttribute("aria-label", /Model uncertainty \(limited tests\): about 65% \(from limited NASA tests\)/);
    await expect(page.getByTestId("drivers-bar")).toHaveAttribute("aria-label", /Flow-mixing coefficient k: 0%, never reaches this band/);
    await expect(page.getByTestId("drivers-bar").locator('[data-source="k"]')).toHaveCount(0);
    await expect(page.getByTestId("share-model_uncertainty")).toHaveText("about 65%");
    await expect(page.getByTestId("drivers-legend")).toContainText("honesty rule for gravity");
    await expect(page.getByTestId("drivers-legend")).toContainText("engineering assumption, not PSI data");
    await expect(page.getByTestId("drivers-legend")).toContainText("Not split (interactions)");
    await expect(page.getByTestId("drivers-lever")).toContainText("Biggest lever");
    const one = page.getByTestId("one-at-a-time");
    await expect(one).not.toHaveAttribute("open", "");
    await one.getByText("One-at-a-time view").click();
    await expect(one).toHaveAttribute("open", "");
    if (SHOTS) await drivers.screenshot({ path: path.join(SHOTS, "bounds-drivers.png") });
    await page.getByTestId("drivers-planner-link").click();
    await expect(page).toHaveURL(/\/planner\?.*#candidate-\d+/);
    const id = new URL(page.url()).hash.slice(1);
    await expect(page.locator(`#${id}`)).toBeInViewport();
  });

  test("lunar base M2 (no evidence) shows no breakdown", async ({ page }) => {
    await page.goto(`/bounds?${LUNAR_BASE}&metric=M2`);
    await expect(page.getByTestId("bounds-extrapolation")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("drivers")).toHaveCount(0);
    await expect(page.getByTestId("drivers-bar")).toHaveCount(0);
  });

  test("offline: the preset breakdown comes from the bundled artifact", async ({ page }) => {
    await blockApi(page);
    await page.goto(`/bounds?${LUNAR_BASE}&metric=M1`);
    await expect(page.getByTestId("drivers")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("share-gravity_widening")).toHaveText("about 25%");
  });

  test("custom habitat: live breakdown, or 'needs the live API' when the API has none (never invented)", async ({ page, request }) => {
    // A cold API can exceed the web client's live timeout; warm this habitat so the live path is exercised.
    await request
      .post(`${API_URL}/bounds`, { data: { g_m_s2: 1.62, p_psia: 8, o2: 0.34, u_cm_s: 10, L_mm: 10, metric: "M1" }, timeout: 60_000 })
      .catch(() => null);
    await page.goto("/bounds?g=1.62&p=8&o2=0.34&u=10&L=10&metric=M1");
    const shown = page.getByTestId("drivers").or(page.getByTestId("drivers-unavailable"));
    await expect(shown).toBeVisible({ timeout: 30_000 });
    if (await page.getByTestId("drivers-unavailable").count()) {
      await expect(page.getByTestId("drivers-unavailable")).toContainText("Needs the live API");
    } else {
      await expect(page.getByText("live API").first()).toBeVisible();
    }
  });
});
