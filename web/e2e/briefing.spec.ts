import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { blockApi, nav } from "./demo-path";

/**
 * S1 habitat fire-safety briefing (/briefing, ADR-0010). Works with the live API or the bundled preset briefings:
 * an API started before POST /briefing existed 404s it, which falls back to artifacts/briefing/{preset}.json.
 */
const LUNAR_BASE = "g=1.62&p=8.2&o2=0.34&u=10&L=10";
const PRESETS = ["iss", "exploration", "lunar_base", "lunar_rover", "mars_base", "earth"] as const;
const ART = (id: string) => JSON.parse(readFileSync(path.resolve(__dirname, `../../artifacts/briefing/${id}.json`), "utf-8"));
const SHOTS = process.env.E2E_SHOTS_DIR;

/** CSS px at 96 dpi; @page margin is 10 mm on every side (app/globals.css). */
const PX_PER_MM = 96 / 25.4;
const MARGIN_MM = 10;
const PAGE_MM = { A4: { w: 210, h: 297 }, Letter: { w: 215.9, h: 279.4 } } as const;

async function openBriefing(page: Page, query: string) {
  await page.goto(`/briefing?${query}`);
  await expect(page.getByTestId("briefing")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/^(live API|offline data)/).first()).toBeVisible();
}

function pdfPages(pdf: Buffer): number {
  return (pdf.toString("latin1").match(/\/Type\s*\/Page(?![s\w])/g) ?? []).length;
}

test.describe("/briefing", () => {
  test("opens from the Briefing button in the habitat bar", async ({ page }) => {
    await page.goto(`/bounds?${LUNAR_BASE}`);
    await page.getByTestId("briefing-button").click();
    await expect(page).toHaveURL(/\/briefing\?/);
    await expect(page.getByRole("heading", { level: 1, name: /^Lunar base: what the evidence can and cannot say about fire/ })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page).toHaveURL(/g=1\.62.*p=8\.2.*o2=0\.34/);
    await expect(nav(page, "Briefing")).toHaveAttribute("aria-current", "page");
  });

  test("lunar base: M2, M4 and M5 are gaps, not numbers; chips use words, icons and rules", async ({ page }) => {
    const art = ART("lunar_base");
    await openBriefing(page, `habitat=lunar_base`);
    await expect(page.getByTestId("briefing-habitat")).toHaveText(art.habitat.line);
    for (const m of ["M2", "M4", "M5"]) {
      await expect(page.getByTestId("gaps").getByTestId(`gap-${m}`)).toContainText("no evidence at this habitat");
      await expect(page.getByTestId(`number-${m}`)).toHaveCount(0);
    }
    await expect(page.getByTestId("number-M1")).toContainText(art.key_numbers[0].text);
    for (const c of art.verdicts) {
      const chip = page.getByTestId(`chip-${c.pillar}`);
      await expect(chip).toHaveAttribute("data-value", c.value);
      await expect(chip.getByTestId("chip-value")).toHaveText(new RegExp(`^${c.value}$`, "i"));
      await expect(chip).toContainText(c.because);
      await expect(chip.locator("svg")).toHaveCount(1);
    }
    const rule = page.getByTestId("chip-prevention").getByTestId("chip-rule");
    await rule.getByText("Rule for this chip").click();
    await expect(rule).toContainText(art.verdicts[0].rule);
    await expect(page.getByTestId("gap-suppression_co2")).toContainText("not an operating procedure");
    await expect(page.getByTestId("next-tests").getByRole("listitem")).toHaveCount(art.next_tests.items.length);
    await expect(page.getByTestId("history")).toContainText(art.history.text);
    await expect(page.getByTestId("trust-line")).toContainText(art.trust.text);
    const footer = page.getByTestId("briefing-footer");
    await expect(footer).toContainText("Not an operating procedure");
    await expect(footer).toContainText("artifact set at build time");
    expect((await page.locator("body").innerText()).toLowerCase()).not.toContain("safest");
    if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "briefing-lunar_base.png"), fullPage: true });
  });

  test("?habitat=<preset> writes the preset into the habitat bar", async ({ page }) => {
    await openBriefing(page, "habitat=iss");
    await expect(page).toHaveURL(/g=0&p=14\.7&o2=0\.21/);
    await expect(page).not.toHaveURL(/habitat=/);
    await expect(page.getByRole("group", { name: "Habitat presets" }).getByRole("button", { name: "ISS", exact: true })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page.getByRole("heading", { level: 1 })).toContainText("ISS");
  });

  test("offline: presets from the bundled briefings; a custom habitat needs the live API", async ({ page }) => {
    await blockApi(page);
    await openBriefing(page, LUNAR_BASE);
    await expect(page.getByText("offline data").first()).toBeVisible();
    await page.getByRole("spinbutton", { name: /Vent speed/ }).fill("7");
    await expect(page.getByText(/Needs the live API: briefings are precomputed only for the six presets/)).toBeVisible();
    await expect(page.getByTestId("briefing")).toHaveCount(0);
  });

  for (const preset of PRESETS) {
    test(`print: ${preset} fits one A4 page and one Letter page, without site chrome`, async ({ page }) => {
      await openBriefing(page, `habitat=${preset}`);
      await page.emulateMedia({ media: "print" });
      await expect(page.getByRole("navigation", { name: "Main" })).toBeHidden();
      await expect(page.getByRole("region", { name: "Habitat settings" })).toBeHidden();
      await expect(page.getByTestId("print-briefing")).toBeHidden();
      await expect(page.getByTestId("chip-value").first()).toBeVisible(); // words, not colour alone
      for (const [name, mm] of Object.entries(PAGE_MM)) {
        const width = Math.floor((mm.w - 2 * MARGIN_MM) * PX_PER_MM);
        const height = Math.floor((mm.h - 2 * MARGIN_MM) * PX_PER_MM);
        await page.setViewportSize({ width, height: 600 });
        const used = await page.evaluate(() => document.documentElement.scrollHeight);
        expect(used, `${preset} ${name}: ${used}px of ${height}px`).toBeLessThanOrEqual(height);
        const pdf = await page.pdf({
          format: name as "A4" | "Letter",
          margin: { top: "10mm", bottom: "10mm", left: "10mm", right: "10mm" },
          printBackground: true,
        });
        expect(pdfPages(pdf), `${preset} ${name} PDF pages`).toBe(1);
      }
      if (SHOTS && preset === "lunar_base") {
        await page.setViewportSize({ width: Math.floor((210 - 20) * PX_PER_MM), height: Math.floor((297 - 20) * PX_PER_MM) });
        await page.screenshot({ path: path.join(SHOTS, "briefing-lunar_base-print.png"), fullPage: true });
      }
    });
  }
});
