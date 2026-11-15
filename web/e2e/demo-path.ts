import { expect, type APIRequestContext, type Page } from "@playwright/test";

/**
 * The scripted 2-minute judge path (plan/11-demo-pitch.md §2), shared by demo.spec.ts (fast, asserted) and
 * record-demo.spec.ts (human pace, video + screenshots). Uses the lunar_base preset: g 1.62, 8.2 psia,
 * O₂ 0.34, vent 10 cm/s, the MIXED-regime case (Ri ≈ 6.48).
 */
export interface DemoHooks {
  /** Called after each step with a stable slug, e.g. to pause or take a screenshot. */
  after?: (step: DemoStep, page: Page) => Promise<void>;
}

export type DemoStep =
  | "01-landing"
  | "02-lunar-base"
  | "03-regime"
  | "04-pressure-gravity"
  | "05-bounds-m1"
  | "06-bounds-m2"
  | "07-explain"
  | "08-ledger"
  | "09-planner";

export const API_URL = process.env.E2E_API_URL ?? "http://127.0.0.1:8000";
export const LUNAR_BASE_HABITAT = { g_m_s2: 1.62, p_psia: 8.2, o2: 0.34, u_cm_s: 10, L_mm: 10 };

/**
 * The first /bounds and /ask calls on a cold API load models and can exceed the web client's 2.5 s live timeout,
 * which (correctly) falls back to offline artifacts. Warm the endpoints the demo uses so the online run is live.
 */
export async function warmApi(request: APIRequestContext) {
  for (const metric of ["M1", "M2"]) {
    await request.post(`${API_URL}/bounds`, { data: { ...LUNAR_BASE_HABITAT, metric }, timeout: 60_000 });
  }
  await request.get(`${API_URL}/metrics`);
  await request.get(`${API_URL}/ledger`);
  await request.get(`${API_URL}/planner`);
  await request.post(`${API_URL}/ask`, {
    data: { question: "Why is there no M2 estimate for the lunar base?", habitat: LUNAR_BASE_HABITAT, context_ids: ["M2"] },
    timeout: 60_000,
  });
}

export const API_PATTERN = /^https?:\/\/(localhost|127\.0\.0\.1|\[::1\]):8000\//;

/** Make the API unreachable for this page (offline mode). */
export async function blockApi(page: Page) {
  await page.route(API_PATTERN, (route) => route.abort("connectionrefused"));
}

export function nav(page: Page, name: string) {
  return page.getByRole("navigation", { name: "Main" }).getByRole("link", { name, exact: true });
}

export async function gotoViaNav(page: Page, name: string, path: RegExp) {
  await nav(page, name).click();
  await expect(page).toHaveURL(path);
}

export function num(text: string | null): number {
  const m = (text ?? "").match(/-?\d+(\.\d+)?/);
  return m ? Number(m[0]) : NaN;
}

export async function landing(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("stops at two gravities");
  // The gap figure (Fig. 4) and the habitat choice on the story page's distribution sheet.
  await expect(page.locator("#gap svg[role='img']").filter({ visible: true })).toHaveAccessibleName(/where NASA has tested fire/i);
  await expect(page.getByRole("group", { name: "Habitat presets" })).toBeAttached();
}

export async function pickLunarBase(page: Page) {
  const btn = page.getByRole("group", { name: "Habitat presets" }).getByRole("button", { name: "Lunar base", exact: true });
  await btn.scrollIntoViewIfNeeded();
  await btn.click();
  await expect(btn).toHaveAttribute("aria-pressed", "true");
  await expect(page).toHaveURL(/g=1\.62.*p=8\.2.*o2=0\.34.*u=10/);
}

export async function regimeMixed(page: Page) {
  await gotoViaNav(page, "Regime", /\/regime\?/);
  const panel = page.getByRole("tabpanel");
  await expect(panel.getByTestId("regime-badge").first()).toHaveText(/mixed/i);
  const ri = num(await panel.getByTestId("stat-ri").textContent());
  expect(ri).toBeGreaterThan(6.3);
  expect(ri).toBeLessThan(6.7);
}

export async function pressureGravity(page: Page) {
  await page.getByRole("tab", { name: /Pressure × gravity/ }).click();
  await expect(page.getByRole("tab", { name: /Pressure × gravity/ })).toHaveAttribute("aria-selected", "true");
  const gs = num(await page.getByTestId("gstar-value").textContent());
  expect(gs).toBeGreaterThan(0.0505);
  expect(gs).toBeLessThan(0.052);
}

export async function boundsM1(page: Page) {
  await gotoViaNav(page, "Bounds", /\/bounds\?/);
  await expect(page.getByRole("button", { name: /^M1/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("bounds-estimate")).toHaveText(/\d+(\.\d)?%/);
  const est = num(await page.getByTestId("bounds-estimate").textContent());
  expect(est).toBeGreaterThan(15);
  expect(est).toBeLessThan(25);
  await expect(page.getByTestId("bounds-band")).toHaveText(/%\s*–\s*\d+(\.\d)?%/);
  await expect(page.getByText(/transfer confidence: low/i)).toBeVisible();
}

export async function boundsM2(page: Page) {
  await page.getByRole("button", { name: /^M2/ }).click();
  await expect(page).toHaveURL(/metric=M2/);
  const box = page.getByTestId("bounds-extrapolation");
  await expect(box).toContainText("Extrapolation: no evidence");
  await expect(box).toContainText(/atmosphere|outside|tested/i);
  await expect(page.getByTestId("bounds-estimate")).toHaveCount(0);
  await expect(box).toContainText("No number is shown on purpose");
}

export async function explain(page: Page) {
  const section = page.getByRole("region", { name: "Explain this prediction" });
  await section.getByRole("button", { name: "Explain", exact: true }).click();
  await expect(section.getByText(/validated: every number and citation traced/)).toBeVisible({ timeout: 30_000 });
  await expect(section.getByRole("heading", { name: "Citations" })).toBeVisible();
}

export async function ledger(page: Page) {
  await gotoViaNav(page, "Ledger", /\/ledger\?/);
  await expect(page.getByTestId("ledger-verified")).toHaveText(/5\s+of\s+5\s+hashes verified/);
}

export async function planner(page: Page) {
  await gotoViaNav(page, "Planner", /\/planner\?/);
  const items = page.getByRole("main").getByRole("listitem").filter({ hasText: /score \d/ });
  await expect(items.first()).toBeVisible();
  expect(await items.count()).toBeGreaterThanOrEqual(5);
  await expect(items.first()).toContainText("#1");
}

/** The full judge path, in the order of plan/11 §2. */
export async function runDemoPath(page: Page, hooks: DemoHooks = {}) {
  const after = hooks.after ?? (async () => {});
  await landing(page);
  await after("01-landing", page);
  await pickLunarBase(page);
  await after("02-lunar-base", page);
  await regimeMixed(page);
  await after("03-regime", page);
  await pressureGravity(page);
  await after("04-pressure-gravity", page);
  await boundsM1(page);
  await after("05-bounds-m1", page);
  await boundsM2(page);
  await after("06-bounds-m2", page);
  await explain(page);
  await after("07-explain", page);
  await ledger(page);
  await after("08-ledger", page);
  await planner(page);
  await after("09-planner", page);
}
