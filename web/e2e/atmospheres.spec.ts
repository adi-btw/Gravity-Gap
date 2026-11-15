import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { blockApi, nav } from "./demo-path";

/**
 * S5 atmosphere evidence map (/atmospheres, ADR-0011). Works with the live API or the bundled artifacts: an API
 * started before GET /atmosphere-map existed 404s it, which falls back to artifacts/atmosphere_map/{metric}_{g}.json.
 */
const LUNAR_BASE = "g=1.62&p=8.2&o2=0.34&u=10&L=10";
const MAP = (m: string, g: string) =>
  JSON.parse(readFileSync(path.resolve(__dirname, `../../artifacts/atmosphere_map/${m}_${g}.json`), "utf-8"));
const SHOTS = process.env.E2E_SHOTS_DIR;

async function openMap(page: Page, query = LUNAR_BASE) {
  await page.goto(`/atmospheres?${query}`);
  await expect(page.getByRole("heading", { level: 1, name: "Which cabin air does the evidence cover?" })).toBeVisible();
  await expect(page.getByTestId("atmosphere-map")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/^(live API|offline data)/).first()).toBeVisible();
}

test.describe("/atmospheres evidence map", () => {
  test("uncovered cells are hatched, never coloured; the evidence share and reading are shown", async ({ page }) => {
    const m1 = MAP("M1", "lunar");
    await openMap(page);
    const cells = page.getByTestId("map-cells").locator("rect");
    await expect(cells).toHaveCount(m1.summary.n_cells);
    const hatched = page.locator('[data-hatch="true"]');
    await expect(hatched).toHaveCount(m1.summary.n_cells - m1.summary.n_covered);
    await expect(hatched.first()).toHaveAttribute("fill", /^url\(#/);
    await expect(page.locator('[data-covered="false"]:not([data-hatch="true"])')).toHaveCount(0);
    await expect(page.locator('[data-covered="true"]').first()).toHaveAttribute("fill", /^#[0-9a-f]{6}$/);
    await expect(page.getByTestId("evidence-share")).toContainText(`${Math.round(m1.summary.evidence_share * 100)}%`);
    await expect(page.getByTestId("evidence-share")).toContainText(`${m1.summary.n_covered} of ${m1.summary.n_cells} cells`);
    await expect(page.getByTestId("evidence-share")).toContainText(`${Math.round(m1.summary.no_evidence_share * 100)}% has no evidence`);
    await expect(page.getByTestId("map-reading")).toHaveText(m1.reading);
    await expect(page.getByTestId("colour-legend")).toContainText("100%");
    await expect(page.getByTestId("colour-legend")).toContainText("No evidence");
    await expect(nav(page, "Air map")).toHaveAttribute("aria-current", "page");
    if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "atmospheres.png"), fullPage: true });
  });

  test("metric and gravity pickers: the coloured cells stay, only the band changes", async ({ page }) => {
    await openMap(page);
    await page.getByRole("group", { name: "Metric" }).getByRole("button", { name: /\(M2\)/ }).click();
    await expect(page).toHaveURL(/metric=M2/);
    const m2 = MAP("M2", "mars");
    await expect(page.getByTestId("evidence-share")).toContainText(`${m2.summary.n_covered} of ${m2.summary.n_cells}`);
    await expect(page.getByTestId("colour-legend")).toContainText("mm");
    await page.getByRole("group", { name: "Gravity" }).getByRole("button", { name: "Mars", exact: true }).click();
    await expect(page).toHaveURL(/gravity=mars/);
    await expect(page.getByTestId("gravity-note")).toContainText(`At Mars gravity the band is widened by a factor of ${m2.gravity.widen_factor}`);
    await expect(page.getByTestId("gravity-note")).toContainText("the same at every gravity");
    await expect(page.locator('[data-hatch="true"]')).toHaveCount(m2.summary.n_cells - m2.summary.n_covered);
  });

  test("clicking a cell loads its O₂ and pressure into the habitat bar and offers Bounds / Compare / Briefing", async ({ page }) => {
    const m1 = MAP("M1", "lunar");
    await openMap(page);
    const cell = m1.cells.find((c: { covered: boolean; o2: number; p_psia: number }) => c.covered && c.o2 === 0.29 && c.p_psia > 8.5 && c.p_psia < 9.5);
    await page.locator(`[data-i="${cell.i}"][data-j="${cell.j}"]`).click();
    await expect(page).toHaveURL(new RegExp(`o2=${cell.o2}(&|$)`));
    await expect(page).toHaveURL(new RegExp(`p=${cell.p_psia}(&|$)`));
    await expect(page).toHaveURL(/g=1\.62/);
    await expect(page.getByRole("spinbutton", { name: /O₂/ })).toHaveValue("29");
    const links = page.getByTestId("loaded-links");
    await expect(links).toBeVisible();
    for (const name of ["Bounds", "Compare", "Briefing"]) {
      await expect(links.getByRole("link", { name })).toHaveAttribute("href", new RegExp(`o2=${cell.o2}`));
    }
    await links.getByRole("link", { name: "Bounds" }).click();
    await expect(page).toHaveURL(new RegExp(`/bounds\\?.*o2=${cell.o2}`));
  });

  test("keyboard: arrow keys move between cells and Enter loads the atmosphere", async ({ page }) => {
    await openMap(page);
    const grid = page.getByTestId("map-keyboard");
    await grid.focus();
    const before = await page.getByTestId("cell-info").innerText();
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("ArrowLeft");
    await page.keyboard.press("ArrowUp");
    await expect(page.getByTestId("cell-info")).not.toHaveText(before);
    await expect(page.getByTestId("cell-info")).toContainText("32% O₂");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/o2=0\.32/);
    await expect(page.getByTestId("loaded-links")).toBeVisible();
  });

  test("crew limits: legend entries with sources, drawn apart from the evidence colours; never 'safest'", async ({ page }) => {
    const crew = MAP("M1", "lunar").overlays.crew_limits;
    await openMap(page);
    const legend = page.getByTestId("crew-legend");
    await expect(legend.locator("ol > li")).toHaveCount(crew.drawn.length);
    await expect(legend.getByTestId("crew-source")).toHaveCount(crew.drawn.length);
    for (const c of crew.drawn) {
      await expect(legend.getByTestId(`crew-${c.id}`)).toContainText(c.label);
      await expect(legend.getByTestId(`crew-${c.id}`).getByTestId("crew-source")).toContainText(c.source.title);
    }
    await expect(legend.getByTestId("crew-o2_max_lsam_2007_baseline")).toContainText("2007 program baseline (materials)");
    await expect(legend.getByTestId("crew-pio2_absolute_hypoxia_floor")).toContainText("absolute floor");
    await expect(legend.getByTestId("crew-pio2_normoxia_target_low")).toContainText("target, not a limit");
    await expect(legend).toContainText("Not drawn: O2 at most 70%");
    // Lines use plain ink, never the viridis fills.
    const strokes = await page.locator('[data-testid="overlay-crew-layer"] path').evaluateAll((els) => els.map((e) => e.getAttribute("stroke")));
    expect(strokes.every((s) => s === "var(--fg)" || s === "var(--surface)" || s === null)).toBe(true);
    await page.getByTestId("overlay-crew").uncheck();
    await expect(page.getByTestId("overlay-crew-layer")).toHaveCount(0);
    // Incidents: assumed atmospheres are marked; Apollo 1 is off this map.
    await expect(page.getByTestId("incident-list")).toContainText("Mir oxygen-generator fire (1997): 21% O₂ at 14.7 psia, assumed atmosphere");
    await expect(page.getByTestId("incident-list")).toContainText("Apollo 1 (1967): 100% O₂ at 16.7 psia, off this map");
    await page.getByTestId("table-toggle").click();
    await expect(page.getByTestId("map-table").locator("tbody tr")).toHaveCount(20);
    expect((await page.locator("body").innerText()).toLowerCase()).not.toContain("safest");
  });

  test("offline: renders from the bundled artifact", async ({ page }) => {
    await blockApi(page);
    await openMap(page, `${LUNAR_BASE}&metric=M3&gravity=orbit`);
    await expect(page.getByText("offline data").first()).toBeVisible();
    const m3 = MAP("M3", "orbit");
    await expect(page.getByTestId("evidence-share")).toContainText(`${m3.summary.n_covered} of ${m3.summary.n_cells}`);
  });
});
