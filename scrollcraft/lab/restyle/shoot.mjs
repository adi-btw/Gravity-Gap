import { createRequire } from "node:module";
const require = createRequire("C:/Users/adity/Downloads/NASA Hackathon/web/package.json");
const { chromium } = require("@playwright/test");
const OUT = "C:/Users/adity/Downloads/NASA Hackathon/scrollcraft/lab/restyle/";
const LB = "g=1.62&p=8.2&o2=0.34&u=10&L=10";
const ROUTES = [
  ["bounds", `/bounds?${LB}&metric=M1`],
  ["compare", `/compare?a=iss&b=lunar_base&${LB}`],
  ["trust", `/trust?${LB}`],
  ["briefing", `/briefing?habitat=lunar_base`],
  ["atmospheres", `/atmospheres?${LB}`],
  ["regime", `/regime?${LB}`],
];
const only = process.argv[2] ? process.argv[2].split(",") : null;
const themes = (process.argv[3] ?? "light,dark").split(",");
const sizes = (process.argv[4] ?? "desk,phone").split(",");
const browser = await chromium.launch();
for (const theme of themes) {
  for (const size of sizes) {
    const ctx = await browser.newContext(size === "phone" ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 } : { viewport: { width: 1440, height: 900 } });
    await ctx.addInitScript((t) => localStorage.setItem("gg-theme", t), theme);
    const page = await ctx.newPage();
    for (const [name, url] of ROUTES) {
      if (only && !only.includes(name)) continue;
      for (let i = 0; i < 3; i++) {
        try { await page.goto("http://localhost:3000" + url, { waitUntil: "networkidle", timeout: 60000 }); break; }
        catch (e) { if (i === 2) throw e; await page.waitForTimeout(2000); }
      }
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${OUT}${name}-${theme === "light" ? "paper" : "night"}-${size}.png`, fullPage: true });
      console.log("shot", name, theme, size);
    }
    await ctx.close();
  }
}
await browser.close();
