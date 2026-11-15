import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/** T8: axe-core on every route and the open Ask drawer, in both themes; zero serious/critical violations. */
const LUNAR_BASE = "g=1.62&p=8.2&o2=0.34&u=10&L=10";
const ROUTES = [
  "/",
  "/regime",
  "/regime?tab=pressure",
  "/explore",
  "/bounds",
  "/investigations/PSI-69",
  "/ledger",
  "/planner",
  "/data",
  "/about",
  "/replay",
  "/suppression",
  "/suppression?g=0&p=14.7&o2=0.21&u=10&L=10&diluent=co2",
  "/detection",
  "/detection?material=Kapton&cut=big_only",
];
const THEMES = ["dark", "light"] as const;
type Theme = (typeof THEMES)[number];

function withHabitat(route: string) {
  return route.includes("?") ? `${route}&${LUNAR_BASE}` : `${route}?${LUNAR_BASE}`;
}

async function setTheme(page: Page, theme: Theme) {
  await page.addInitScript((t) => {
    try {
      localStorage.setItem("gg-theme", t);
    } catch {
      /* ignore */
    }
  }, theme);
}

/** Wait for the page's async panels to settle (no loading spinners left). */
async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.locator('[role="status"]').filter({ hasText: /Loading|Computing|Thinking/ })).toHaveCount(0, {
    timeout: 20_000,
  });
}

async function audit(page: Page, label: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"])
    .analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  const summary = bad.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes
      .slice(0, 6)
      .map((n) => `${n.target.join(" ")} :: ${(n.failureSummary ?? "").split("\n").slice(1, 2).join(" ")}`),
  }));
  expect(summary, `${label}: serious/critical axe violations`).toEqual([]);
}

for (const theme of THEMES) {
  test.describe(`axe (${theme} theme)`, () => {
    test.beforeEach(async ({ page }) => {
      await setTheme(page, theme);
    });

    for (const route of ROUTES) {
      test(route, async ({ page }) => {
        await page.goto(withHabitat(route));
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await settle(page);
        await audit(page, `${route} [${theme}]`);
      });
    }

    test("open Ask drawer with an answer", async ({ page }) => {
      await page.goto(withHabitat("/bounds"));
      await settle(page);
      await page.getByRole("button", { name: "Ask", exact: true }).click();
      const dialog = page.getByRole("dialog", { name: "Ask Gravity Gap" });
      await dialog.getByRole("button", { name: "What should LUCI test first?" }).click();
      await dialog.getByRole("button", { name: "Ask", exact: true }).click();
      await expect(dialog.getByRole("heading", { name: "Citations" })).toBeVisible({ timeout: 30_000 });
      await audit(page, `Ask drawer [${theme}]`);
    });

    test("bounds M2 extrapolation state and Explain answer", async ({ page }) => {
      await page.goto(`/bounds?${LUNAR_BASE}&metric=M2`);
      await settle(page);
      await page
        .getByRole("region", { name: "Explain this prediction" })
        .getByRole("button", { name: "Explain", exact: true })
        .click();
      await expect(page.getByText(/validated: every number/)).toBeVisible({ timeout: 30_000 });
      await audit(page, `bounds M2 + explain [${theme}]`);
    });
  });
}

test.describe("keyboard only", () => {
  type Focused = { tag: string; text: string; label: string };

  async function tabTo(page: Page, match: (el: Focused) => boolean, max = 60) {
    for (let i = 0; i < max; i++) {
      await page.keyboard.press("Tab");
      const el = await page.evaluate(() => {
        const a = document.activeElement as HTMLElement | null;
        return { tag: a?.tagName ?? "", text: (a?.textContent ?? "").trim(), label: a?.getAttribute("aria-label") ?? "" };
      });
      if (match(el)) return;
    }
    throw new Error("element not reached by Tab");
  }

  async function focusRingVisible(page: Page) {
    const outline = await page.evaluate(() => {
      const s = getComputedStyle(document.activeElement as HTMLElement);
      return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) };
    });
    expect(outline.style).not.toBe("none");
    expect(outline.width).toBeGreaterThanOrEqual(2);
  }

  test("skip link, HabitatBar presets and fields are reachable and operable", async ({ page }) => {
    await page.goto("/regime");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
    await focusRingVisible(page);

    await tabTo(page, (el) => el.tag === "BUTTON" && el.text === "Lunar base");
    await focusRingVisible(page);
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Lunar base", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("regime-badge").first()).toHaveText(/mixed/i);

    // Gravity slider, then its numeric input.
    await tabTo(page, (el) => el.tag === "INPUT" && /Gravity slider/.test(el.label));
    await focusRingVisible(page);
    await page.keyboard.press("Tab");
    const gInput = page.getByRole("spinbutton", { name: /Gravity/ });
    await expect(gInput).toBeFocused();
    await page.keyboard.press("Control+A");
    await page.keyboard.type("9.81");
    await expect(page).toHaveURL(/g=9\.81/);
    await expect(page.getByTestId("regime-badge").first()).toHaveText(/buoyant/i);

    // Every other HabitatBar field (slider, then number input) is reachable in order.
    for (const name of [/Cabin pressure/, /O₂/, /Vent speed/, /Flame size/]) {
      await page.keyboard.press("Tab");
      await expect(page.getByRole("slider", { name })).toBeFocused();
      await page.keyboard.press("Tab");
      await expect(page.getByRole("spinbutton", { name })).toBeFocused();
    }
  });

  test("Ask drawer opens and closes with the keyboard and traps focus", async ({ page }) => {
    await page.goto(`/bounds?${LUNAR_BASE}`);
    await tabTo(page, (el) => el.tag === "BUTTON" && el.text === "Ask");
    await focusRingVisible(page);
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "Ask Gravity Gap" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("textbox", { name: "Your question" })).toBeFocused();

    // Focus stays inside the dialog while tabbing either way.
    for (let i = 0; i < 15; i++) {
      await page.keyboard.press("Tab");
      expect(await dialog.evaluate((d) => d.contains(document.activeElement))).toBe(true);
    }
    for (let i = 0; i < 3; i++) {
      await page.keyboard.press("Shift+Tab");
      expect(await dialog.evaluate((d) => d.contains(document.activeElement))).toBe(true);
    }

    // Type and send with Ctrl+Enter.
    await dialog.getByRole("textbox", { name: "Your question" }).focus();
    await page.keyboard.type("What should LUCI test first?");
    await page.keyboard.press("Control+Enter");
    await expect(dialog.getByRole("heading", { name: "Citations" })).toBeVisible({ timeout: 30_000 });

    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    const askBtn = page.getByRole("button", { name: "Ask", exact: true });
    await expect(askBtn).toBeFocused();

    // Re-open and close with the Close button, keyboard only.
    await page.keyboard.press("Enter");
    await expect(dialog).toBeVisible();
    await tabTo(page, (el) => el.tag === "BUTTON" && /^Close/.test(el.text), 20);
    await page.keyboard.press("Enter");
    await expect(dialog).toHaveCount(0);
    await expect(askBtn).toBeFocused();
  });

  test("regime tabs switch with arrow keys", async ({ page }) => {
    await page.goto(`/regime?${LUNAR_BASE}`);
    await page.getByRole("tab", { name: /Flame regime/ }).focus();
    await page.keyboard.press("ArrowRight");
    const pressure = page.getByRole("tab", { name: /Pressure × gravity/ });
    await expect(pressure).toBeFocused();
    await expect(pressure).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("gstar-value")).toBeVisible();
  });
});
