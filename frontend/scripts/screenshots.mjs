// Screenshots of the main screens at phone and laptop width, light and dark, for
// design reviews. Needs the app running (vite preview or dev) with the API behind it.
//   npm run screenshots -- http://localhost:4183 out-dir
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const base = process.argv[2] ?? "http://localhost:4183";
const out = process.argv[3] ?? "screenshots";
mkdirSync(out, { recursive: true });

const sizes = {
  phone: { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  laptop: { viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1 },
};
// [file name, persona to sign in as (null = signed out), path]
const shots = [
  ["welcome", null, "/welcome"],
  ["student-home", "Ravi", "/map"],
  ["student-me", "Ravi", "/me"],
  ["founder-home", "Meera", "/matches"],
  ["partner-home", "Nandini", "/dashboard"],
];

const browser = await chromium.launch();
for (const [size, options] of Object.entries(sizes)) {
  for (const scheme of ["light", "dark"]) {
    const context = await browser.newContext({ ...options, colorScheme: scheme, serviceWorkers: "block" });
    const page = await context.newPage();
    for (const [name, persona, path] of shots) {
      if (scheme === "dark" && !["welcome", "student-me"].includes(name)) continue;
      await page.goto(`${base}/welcome`);
      await page.evaluate(() => localStorage.clear());
      if (persona) {
        await page.goto(`${base}/welcome`);
        await page.getByRole("button", { name: new RegExp(persona) }).click();
        await page.getByRole("navigation", { name: "Main" }).waitFor();
      }
      await page.goto(`${base}${path}`);
      await page.waitForLoadState("networkidle");
      const file = `${out}/${size}-${scheme}-${name}.png`;
      await page.screenshot({ path: file, fullPage: false });
      console.log(file);
    }
    await context.close();
  }
}
await browser.close();
