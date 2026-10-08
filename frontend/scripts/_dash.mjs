import { chromium } from "@playwright/test";
const [out] = process.argv.slice(2);
const b = await chromium.launch();
for (const [size, opts] of [["phone", { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }], ["laptop", { viewport: { width: 1280, height: 800 } }]]) {
  const p = await (await b.newContext({ ...opts, serviceWorkers: "block" })).newPage();
  p.on("console", (m) => m.type() === "error" && console.log("console:", m.text()));
  await p.goto("http://localhost:4183/welcome"); await p.getByRole("button", { name: /^Nandini/ }).click();
  await p.getByRole("navigation", { name: "Main" }).waitFor(); await p.goto("http://localhost:4183/dashboard");
  await p.locator("[data-heat-settled]").waitFor({ timeout: 20000 }); await p.waitForTimeout(800);
  await p.screenshot({ path: `${out}/${size}-dashboard.png`, fullPage: true });
}
await b.close();
