import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

/**
 * The story page at "/" (scrollcraft/builds/gravity-gap/SCORE.md): a scroll-driven evidence report that leads into
 * the tool. These checks cover its real behaviour, not its pixels: reading order, the honesty figure, credits, the
 * habitat choice and the one action, plus the phone and reduced-motion floors.
 */

const M2 = JSON.parse(
  readFileSync(path.join(__dirname, "..", "..", "artifacts", "bounds", "lunar_base_M2.json"), "utf-8"),
) as { applicable: boolean; evidence: { distance: number }[] };

async function visibleText(page: Page) {
  return page.evaluate(() => document.querySelector(".gg-story")?.textContent ?? "");
}

test.describe("story page", () => {
  test("renders the report with headings in order", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("NASA's fire data stops at two gravities");
    const h2 = await page.locator(".gg-story h2").allTextContents();
    expect(h2.map((t) => t.trim())).toEqual([
      "Fire is the emergency every crew plans for",
      "Every one of those tests burned at one of two gravities",
      "Two ends, and nothing in the middle",
      "Gravity Gap carries the orbit tests across, and pays for it in width",
      "Where the evidence stops, the numbers stop",
      "Choose the habitat for your copy",
    ]);
    // Only one h1, and the engine mounted.
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.locator("html")).toHaveClass(/sc-ready/);
  });

  test("the refusal figure shows 'no evidence' with the real M2 distance", async ({ page }) => {
    expect(M2.applicable).toBe(false);
    const distance = M2.evidence[0].distance.toFixed(2);
    await page.goto("/");
    const section = page.locator("#refusal");
    // Scroll through the pinned act to the end of the press.
    await section.evaluate((el) => window.scrollTo({ top: el.getBoundingClientRect().top + scrollY + el.getBoundingClientRect().height - innerHeight, behavior: "instant" }));
    const stamp = page.getByTestId("refusal-stamp");
    await expect(stamp).toHaveText(/no evidence/i);
    await expect.poll(async () => Number(await stamp.evaluate((e) => getComputedStyle(e).opacity))).toBeGreaterThan(0.95);
    await expect(section.getByRole("img", { name: /Distance from the lunar-base air/ })).toBeVisible();
    await expect(section.locator("desc#gauge-d")).toContainText(`distance of ${distance}`);
    await expect(section.getByText(`Nearest test: PSI-69`)).toBeVisible();
    await expect(section.getByRole("row", { name: /M2/ })).toContainText(/no evidence/i);

    // The replay control is keyboard operable and ends on the same refusal.
    const again = section.getByRole("button", { name: "Try to print M2 again" });
    await again.focus();
    await page.keyboard.press("Enter");
    await expect(section.getByRole("status")).toContainText(`Distance ${distance} is past the gate`, { timeout: 8_000 });
  });

  test("credits and the independence line are present", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("independence-line")).toHaveText(
      "Gravity Gap is an independent NASA Space Apps 2026 project. It is not a NASA product.",
    );
    for (const id of ["as11-44-6549", "iss071e582160", "iss040e072900", "GRC-1998-C-00486"]) {
      await expect(page.getByRole("link", { name: id, exact: true })).toHaveAttribute(
        "href",
        `https://images.nasa.gov/details/${id}`,
      );
    }
    await expect(page.getByText(/CC0-1\.0/)).toBeVisible();
  });

  test("no em dash in visible text", async ({ page }) => {
    await page.goto("/");
    const text = await visibleText(page);
    expect(text.length).toBeGreaterThan(1000);
    expect(text).not.toContain("—");
  });

  test("habitat choice writes the URL and the one action opens the tool on it", async ({ page }) => {
    await page.goto("/");
    const group = page.getByRole("group", { name: "Habitat presets" });
    const mars = group.getByRole("button", { name: "Mars base", exact: true });
    await mars.scrollIntoViewIfNeeded();
    await mars.click();
    await expect(mars).toHaveAttribute("aria-pressed", "true");
    await expect(page).toHaveURL(/g=3\.71.*p=8\.2.*o2=0\.34/);
    await expect(page.getByText(/Mars base.*regime, Richardson number/)).toBeVisible();
    const cta = page.getByRole("link", { name: "Open the tool", exact: true });
    await expect(cta).toHaveCount(1);
    await cta.click();
    await expect(page).toHaveURL(/\/bounds\?g=3\.71/);
  });

  test("phone width: no horizontal scroll", async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    for (const frac of [0, 0.25, 0.5, 0.75, 1]) {
      await page.evaluate((f) => window.scrollTo(0, (document.documentElement.scrollHeight - innerHeight) * f), frac);
      const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(over, `horizontal overflow at ${frac}`).toBeLessThanOrEqual(0);
    }
    await ctx.close();
  });

  test("reduced motion renders every figure complete without pinned travel", async ({ browser }) => {
    const ctx = await browser.newContext({ reducedMotion: "reduce", viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();
    await page.goto("/");
    await expect(page.locator("html")).toHaveClass(/sc-ready/);
    // No act owns extra scroll room.
    for (const id of ["gap", "refusal"]) {
      const h = await page.locator(`#${id}`).evaluate((el) => el.getBoundingClientRect().height / innerHeight);
      expect(h, `#${id} height in screens`).toBeLessThan(1.6);
    }
    // Static end states: the stamp and the Moon/Mars markers are fully drawn, flow content is not hidden.
    expect(Number(await page.getByTestId("refusal-stamp").evaluate((e) => getComputedStyle(e).opacity))).toBe(1);
    expect(Number(await page.locator("#gap .gg-gap__h .gg-drop-mars").evaluate((e) => getComputedStyle(e).opacity))).toBe(1);
    await page.locator("#distribution").scrollIntoViewIfNeeded();
    for (const sel of ["#hazard h2", "#two-gravities h2", "#bridge h2", ".gg-between p"]) {
      await page.locator(sel).scrollIntoViewIfNeeded();
      await expect.poll(async () => Number(await page.locator(sel).evaluate((e) => getComputedStyle(e.closest("[data-sc-in]") ?? e).opacity))).toBe(1);
    }
    // Both candle photographs are visible side by side.
    await expect(page.getByRole("img", { name: /On Earth: a tall/ })).toBeVisible();
    await expect(page.getByRole("img", { name: /In microgravity: the same candle/ })).toBeVisible();
    await ctx.close();
  });
});
