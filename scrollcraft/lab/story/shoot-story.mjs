// Story-page shooter: walks each section of "/" at several positions, per viewport, theme and motion setting.
// Run from web/ so playwright-core resolves: node ../scrollcraft/lab/story/shoot-story.mjs <variant> [url]
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
const { chromium } = createRequire(path.join(process.cwd(), "package.json"))("playwright-core");
const variant = process.argv[2] ?? "desktop-light";
const TARGET = process.argv[3] ?? "http://localhost:3000/";
const [form, theme, motion] = variant.split("-");
const vp = form === "phone" ? { width: 390, height: 844 } : { width: 1440, height: 900 };
import { fileURLToPath } from "node:url";
const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), variant);
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });
const CHROME = ["C:/Program Files/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"].find((p) => fs.existsSync(p));
const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: 1, reducedMotion: motion === "reduced" ? "reduce" : "no-preference", isMobile: form === "phone", hasTouch: form === "phone" });
await ctx.addInitScript((t) => { try { localStorage.setItem("gg-theme", t); } catch {} }, theme === "dark" ? "dark" : "light");
const page = await ctx.newPage();
const errors = [];
page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") errors.push(`${m.type()}: ${m.text()}`); });
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
page.on("requestfailed", (r) => errors.push(`failed: ${r.url()}`));
await page.goto(TARGET, { waitUntil: "networkidle" });
await page.waitForFunction(() => document.documentElement.classList.contains("sc-ready"), null, { timeout: 15000 }).catch(() => errors.push("engine never mounted"));
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(600);
const plan = await page.evaluate(() => {
  const ids = ["cover", "hazard", "two-gravities", null, "gap", "bridge", "refusal", "distribution"];
  const secs = [...document.querySelectorAll(".gg-story > section")];
  const vh = innerHeight;
  const out = [];
  secs.forEach((s, i) => {
    const r = s.getBoundingClientRect();
    const top = r.top + scrollY, h = r.height;
    const name = s.id || "between";
    const pinned = s.getAttribute("data-sc-act") === "pin" && h > vh * 1.2;
    const ps = pinned ? [0, 0.2, 0.4, 0.55, 0.62, 0.7, 0.85, 1] : name === "cover" ? [0, 0.35, 0.7] : [-0.35, 0, 0.5];
    for (const p of ps) {
      const y = pinned ? top + (h - vh) * p : name === "cover" ? top + h * p - (top) : top + (p < 0 ? vh * p : p === 0 ? 0 : Math.max(0, h - vh) * p);
      out.push({ name, p, y: Math.max(0, Math.round(y)) });
    }
  });
  return { out, total: document.documentElement.scrollHeight, vh, vw: innerWidth, sw: document.documentElement.scrollWidth };
});
let k = 0;
for (const s of plan.out) {
  await page.evaluate((y) => window.scrollTo({ top: y, behavior: "instant" }), s.y);
  await page.waitForTimeout(motion === "reduced" ? 250 : 450);
  const f = `${String(++k).padStart(2, "0")}-${s.name}-${String(s.p).replace("-", "m")}.png`;
  await page.screenshot({ path: path.join(OUT, f) });
}
const report = { variant, total: plan.total, vh: plan.vh, vw: plan.vw, scrollWidth: plan.sw, docHeightInScreens: (plan.total / plan.vh).toFixed(2), errors };
fs.writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
await browser.close();
