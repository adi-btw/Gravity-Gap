// Scratch screenshot runner for the unslop pass. Usage: node unslop/shoot.cjs <before|after> [filter]
const path = require("node:path");
const fs = require("node:fs");
const { chromium } = require(path.join(__dirname, "..", "web", "node_modules", "@playwright", "test"));

const out = path.join(__dirname, "shots", process.argv[2] || "after");
const filter = process.argv[3] || "";
fs.mkdirSync(out, { recursive: true });
const BASE = process.env.BASE || "http://localhost:3000";
const LB = "g=1.62&p=8.2&o2=0.34&u=10&L=10";

const PAGES = [
  ["home", "/", [0, 0.5, 1, 1.6, 2.4, 3.4, 4.5, 6, 8, 10]],
  ["bounds", `/bounds?${LB}&metric=M1`],
  ["compare", "/compare?a=iss&b=lunar_base"],
  ["briefing", "/briefing?habitat=lunar_base"],
  ["trust", `/trust?${LB}`],
  ["atmospheres", `/atmospheres?${LB}`],
  ["regime", `/regime?${LB}`],
  ["explore", `/explore?${LB}`],
  ["planner", `/planner?${LB}`],
];
const VIEWS = [
  ["d", 1440, 900],
  ["m", 390, 844],
];

(async () => {
  const browser = await chromium.launch();
  for (const theme of ["light", "dark"]) {
    for (const [vk, w, h] of VIEWS) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
      await ctx.addInitScript((t) => localStorage.setItem("gg-theme", t), theme);
      const page = await ctx.newPage();
      for (const [name, url, scrolls] of PAGES) {
        if (filter && !name.includes(filter)) continue;
        try {
          await page.goto(BASE + url, { waitUntil: "networkidle", timeout: 60000 });
        } catch (e) {
          console.log("timeout", name);
        }
        try {
          await page.waitForFunction(
            () => ![...document.querySelectorAll('[role="status"]')].some((e) => /Loading|Computing|Thinking/.test(e.textContent || "")),
            null,
            { timeout: 45000 },
          );
        } catch {
          console.log("still loading", name);
        }
        await page.waitForTimeout(1200);
        if (scrolls) {
          // walk down so reveal-on-scroll sections settle, then capture each stop
          for (const s of scrolls) {
            await page.evaluate((k) => window.scrollTo({ top: k * innerHeight, behavior: "instant" }), s);
            await page.waitForTimeout(700);
            await page.screenshot({ path: path.join(out, `${name}-${String(s).replace(".", "_")}-${vk}-${theme}.png`) });
          }
        } else {
          await page.screenshot({ path: path.join(out, `${name}-${vk}-${theme}.png`), fullPage: true });
        }
        console.log("ok", name, vk, theme);
      }
      await ctx.close();
    }
  }
  await browser.close();
})();
