import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { runDemoPath, warmApi, type DemoStep } from "./demo-path";

/**
 * H4 demo media: runs the judge path at a human pace with video on (1440×900) and writes
 * docs/media/demo.webm plus one screenshot per step. Run with `npm run record-demo`
 * (playwright.record.config.ts); excluded from `npm run e2e`.
 */
const MEDIA = path.resolve(__dirname, "..", "..", "docs", "media");

/** Seconds to linger on each screen so a viewer can read it (total stays under 2 minutes). */
const PAUSE: Record<DemoStep, number> = {
  "01-landing": 7,
  "02-lunar-base": 5,
  "03-regime": 9,
  "04-pressure-gravity": 9,
  "05-bounds-m1": 11,
  "06-bounds-m2": 8,
  "07-explain": 11,
  "08-ledger": 8,
  "09-planner": 9,
};

/** Screenshot names, following the plan/11 storyboard. */
const SHOT: Partial<Record<DemoStep, string>> = {
  "01-landing": "01-landing.png",
  "03-regime": "02-regime-mixed.png",
  "04-pressure-gravity": "03-pressure-gravity.png",
  "05-bounds-m1": "04-bounds-m1.png",
  "06-bounds-m2": "05-bounds-m2-extrapolation.png",
  "07-explain": "06-explain.png",
  "08-ledger": "07-ledger.png",
  "09-planner": "08-planner.png",
};

// Warm before the page (and its video) exists, so the recording does not open on a blank wait.
test.beforeAll(async ({ request }) => {
  await warmApi(request);
});

test("record the demo path", async ({ page }) => {
  fs.mkdirSync(MEDIA, { recursive: true });
  await runDemoPath(page, {
    after: async (step, p) => {
      if (step === "07-explain") {
        await p.getByRole("region", { name: "Explain this prediction" }).scrollIntoViewIfNeeded();
      } else {
        await p.evaluate(() => window.scrollTo({ top: 0 }));
      }
      // The recording must show the live API, not the offline fallback.
      if (step === "05-bounds-m1" || step === "07-explain") {
        await expect(p.getByText("offline data")).toHaveCount(0);
      }
      await p.waitForTimeout(400); // let nav color transitions finish before the still
      const shot = SHOT[step];
      if (shot) await p.screenshot({ path: path.join(MEDIA, shot) });
      // Scroll the long pages slowly so the video shows the evidence below the fold.
      if (step === "05-bounds-m1" || step === "09-planner") {
        await p.waitForTimeout((PAUSE[step] * 1000) / 2);
        await p.mouse.wheel(0, 600);
        await p.waitForTimeout((PAUSE[step] * 1000) / 2);
      } else {
        await p.waitForTimeout(PAUSE[step] * 1000);
      }
    },
  });

  const video = page.video();
  await page.close();
  if (video) await video.saveAs(path.join(MEDIA, "demo.webm"));
});
