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
// [file name, persona to sign in as (null = signed out), path, then (optional)]
const pin = (name) => async (page) => {
  await page.locator("[data-map-settled]").waitFor();
  await page.getByRole("button", { name: new RegExp(`^${name}, `) }).dispatchEvent("click");
};
const firstJob = async (page) => {
  await page.getByRole("main").getByRole("link").filter({ hasText: /\d+%\s*match/ }).first().click();
  await page.getByRole("button", { name: "Apply" }).waitFor();
};
const shots = [
  ["welcome", null, "/welcome"],
  ["founder-matches", "Meera", "/matches"],
  ["student-me", "Ravi", "/me"],
  ["switcher", "Ravi", "/me", async (page) => page.getByRole("button", { name: "Switch person" }).click()],
  ["student-map", "Ravi", "/map", async (page) => page.locator("[data-map-settled]").waitFor()],
  ["student-map-pin", "Ravi", "/map", pin("LedgerLoop")],
  ["student-jobs", "Ravi", "/jobs", async (page) =>
    page.getByRole("main").getByRole("link").filter({ hasText: /\d+%\s*match/ }).first().waitFor()],
  ["student-job", "Ravi", "/jobs", firstJob],
  ["founder-startup", "Rohan", "/startups", async (page) => {
    await page.getByLabel("Startup name").fill("TerraGrid");
    await page.getByRole("link", { name: /TerraGrid/ }).click();
    await page.getByRole("button", { name: "Claim this startup" }).waitFor();
  }],
  ["founder-applicants", "Deepak", "/me", async (page) => {
    await page.getByRole("link", { name: /LedgerLoop/ }).click();
    await page.getByRole("link", { name: "See applicants" }).click();
    await page.getByRole("heading", { name: "Applicants" }).waitFor();
  }],
  ["partner-map", "Nandini", "/map", async (page) => page.locator("[data-map-settled]").waitFor()],
  ["founder-onboarding", "Meera", "/me/profile", async (page) =>
    page.getByRole("button", { name: "Save and see matches" }).waitFor()],
  ["founder-intro-sheet", "Rohan", "/matches", async (page) => {
    await page.getByRole("article").filter({ hasText: "Vikram Shah" }).getByRole("button", { name: "Ask for intro" }).click();
    await page.getByTestId("intro-path").waitFor();
  }],
  ["mentor-intros", "Lakshmi", "/intros", async (page) => page.getByTestId("intro-capacity").waitFor()],
  ["partner-dashboard", "Nandini", "/dashboard", async (page) => {
    await page.getByText("Show as a table").waitFor();
    await page.mouse.move(0, 0); // no chart tooltip in the picture
  }],
  ["partner-gap-map", "Nandini", "/dashboard", async (page) => {
    await page.getByRole("img", { name: /^Map of where/ }).scrollIntoViewIfNeeded();
    await page.locator("[data-heat-settled]").waitFor();
  }],
  // Runs a real round (changes the database): run `make reset-demo` afterwards.
  ["partner-run-round", "Nandini", "/dashboard", async (page) => {
    await page.getByRole("button", { name: "Run round now" }).click();
    await page.getByRole("status").waitFor();
  }],
  ["founder-circuits", "Asha", "/circuits", async (page) => page.getByTestId("loop-card").waitFor()],
];

const browser = await chromium.launch();
for (const [size, options] of Object.entries(sizes)) {
  {
    const context = await browser.newContext({ ...options, colorScheme: "dark", serviceWorkers: "block" });
    const page = await context.newPage();
    for (const [name, persona, path, then] of shots) {
      await page.goto(`${base}/welcome`);
      await page.evaluate(() => localStorage.clear());
      if (persona) {
        await page.goto(`${base}/welcome`);
        await page.getByRole("button", { name: new RegExp(`^(Dr\\. )?${persona}`) }).click();
        await page.getByRole("navigation", { name: "Main" }).waitFor();
      }
      await page.goto(`${base}${path}`);
      await page.waitForLoadState("load");
      if (then) {
        await then(page);
        await page.waitForTimeout(400); // let sheets and the map finish moving
      }
      const file = `${out}/${size}-${name}.png`;
      await page.screenshot({ path: file, fullPage: false });
      console.log(file);
    }
    await context.close();
  }
}
await browser.close();
