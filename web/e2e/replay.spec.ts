import { expect, test, type Page } from "@playwright/test";
import { API_URL, blockApi } from "./demo-path";

/** R1 real-fire replay (plan/13-round-2-features.md): incident cards, scope badge, one-click habitat load. */

function card(page: Page, id: string) {
  return page.getByTestId(`incident-${id}`);
}

async function openReplay(page: Page) {
  await page.goto("/replay");
  await expect(page.getByRole("heading", { level: 1, name: "Real fires, today's data" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Incidents" }).getByRole("article")).toHaveCount(4);
}

test.describe("real-fire replay", () => {
  test.beforeAll(async ({ request }) => {
    // Warm /bounds for the incident habitats so the first live call does not time out into the offline path.
    for (const h of [
      { g_m_s2: 0, p_psia: 14.7, o2: 0.21, u_cm_s: 10, L_mm: 10 },
      { g_m_s2: 9.81, p_psia: 16.7, o2: 1.0, u_cm_s: 10, L_mm: 10 },
    ]) {
      await request.post(`${API_URL}/bounds`, { data: { ...h, metric: "M1" }, timeout: 60_000 }).catch(() => undefined);
    }
  });

  test("renders four incident cards; Apollo 13 is outside scope with no load button", async ({ page }) => {
    await openReplay(page);
    for (const id of ["apollo1", "mir1997", "artemis2"]) {
      await expect(card(page, id).getByRole("button", { name: /Load this habitat/ })).toBeVisible();
      await expect(card(page, id).getByTestId("metric-strip").getByRole("listitem")).toHaveCount(5);
    }
    const a13 = card(page, "apollo13");
    await expect(a13.getByText("Outside scope", { exact: true })).toBeVisible();
    await expect(a13.getByTestId("scope-note")).toBeVisible();
    await expect(a13.getByRole("button", { name: /Load this habitat/ })).toHaveCount(0);

    // Apollo 1's strip says "no evidence" for every metric (the engine's gate, no special-casing).
    await expect(card(page, "apollo1").getByTestId("metric-strip").getByText("no evidence")).toHaveCount(5);

    // Assumptions are explained on the card (Artemis II: the alarm turned the cabin fans off).
    await expect(card(page, "artemis2").getByTestId("assumed-note")).toContainText(/fans/);

    // Source links open safely in a new tab.
    const link = card(page, "apollo1").getByRole("link", { name: /sma\.nasa\.gov/ }).first();
    await expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  test("Load on Mir lands on /bounds at 0 g with a data-source chip", async ({ page }) => {
    await openReplay(page);
    await card(page, "mir1997").getByRole("button", { name: /Load this habitat/ }).click();
    await expect(page).toHaveURL(/\/bounds\?g=0&p=14\.7&o2=0\.21&u=10&L=10/);
    await expect(page.getByText(/^(live API|offline data)$/).first()).toBeVisible();
    await expect(page.getByTestId("bounds-estimate")).toBeVisible();
    // History chip for the incident shows as selected.
    await expect(page.getByRole("group", { name: "Real fire incidents" }).getByRole("button", { name: /^Mir/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  test("Load on Apollo 1 keeps 16.7 psia / 100% O2 and shows the no-evidence state", async ({ page }) => {
    await openReplay(page);
    await card(page, "apollo1").getByRole("button", { name: /Load this habitat/ }).click();
    await expect(page).toHaveURL(/\/bounds\?g=9\.81&p=16\.7&o2=1&u=10&L=10/);
    await expect(page.getByRole("spinbutton", { name: /Cabin pressure/ })).toHaveValue("16.7");
    await expect(page.getByRole("spinbutton", { name: /O₂/ })).toHaveValue("100");
    await expect(page.getByTestId("bounds-extrapolation")).toBeVisible();
    await expect(page.getByText("Extrapolation: no evidence", { exact: true })).toBeVisible();
  });

  test("offline: cards come from the bundled artifact and Mir still loads", async ({ page }) => {
    await blockApi(page);
    await openReplay(page);
    await expect(page.getByText("offline data").first()).toBeVisible();
    await card(page, "mir1997").getByRole("button", { name: /Load this habitat/ }).click();
    await expect(page).toHaveURL(/\/bounds\?g=0&/);
    await expect(page.getByText("offline data").first()).toBeVisible();
  });

  test("landing page links to the replay", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /Start with a real fire/ }).click();
    await expect(page).toHaveURL(/\/replay/);
    await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Replay", exact: true })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});
