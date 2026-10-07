// Screenshots of the main screens at phone and laptop width, for design reviews. Needs the app running (vite preview or dev) with the API behind it.
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
// [file name, persona to sign in as (null = signed out), path, open the switcher?]
const shots = [
  ["welcome", null, "/welcome"],
  ["founder-matches", "Meera", "/matches"],
  ["student-me", "Ravi", "/me"],
  ["switcher", "Ravi", "/me", true],
  ["partner-me", "Nandini", "/me"],
];

const browser = await chromium.launch();
for (const [size, options] of Object.entries(sizes)) {
  {
    const context = await browser.newContext({ ...options, colorScheme: "dark", serviceWorkers: "block" });
    const page = await context.newPage();
    for (const [name, persona, path, openSwitcher] of shots) {
      await page.goto(`${base}/welcome`);
      await page.evaluate(() => localStorage.clear());
      if (persona) {
        await page.goto(`${base}/welcome`);
        await page.getByRole("button", { name: new RegExp(`^(Dr\\. )?${persona}`) }).click();
        await page.getByRole("navigation", { name: "Main" }).waitFor();
      }
      await page.goto(`${base}${path}`);
      await page.waitForLoadState("networkidle");
      if (openSwitcher) {
        await page.getByRole("button", { name: "Switch person" }).click();
        await page.waitForLoadState("networkidle");
      }
      const file = `${out}/${size}-${name}.png`;
      await page.screenshot({ path: file, fullPage: false });
      console.log(file);
    }
    await context.close();
  }
}
await browser.close();
