// Lighthouse scores for the built app, as a phone on a slow network sees it
// (Lighthouse's default mobile profile: a mid-range Android, simulated slow 4G).
//
//   npm run build && npx vite preview --port 4183 &   (API on :8000 for live data)
//   npm run lighthouse -- http://localhost:4183/welcome
//
// Uses Playwright's Chromium unless CHROME_PATH is set. Note: Lighthouse 12+ dropped
// its "PWA" category; installability is checked by e2e/pwa.spec.ts instead.
import { chromium } from "@playwright/test";
import * as chromeLauncher from "chrome-launcher";
import lighthouse from "lighthouse";

const url = process.argv[2] ?? "http://localhost:4183/welcome";
const TARGET = 90;
const chrome = await chromeLauncher.launch({
  chromePath: process.env.CHROME_PATH || chromium.executablePath(),
  chromeFlags: ["--headless=new", "--no-sandbox"],
});
try {
  const result = await lighthouse(url, {
    port: chrome.port,
    output: "json",
    logLevel: "error",
    onlyCategories: ["performance", "accessibility", "best-practices", "seo"],
  });
  const { categories, audits } = result.lhr;
  let failed = false;
  console.log(`Lighthouse (mobile, slow 4G) for ${url}`);
  for (const c of Object.values(categories)) {
    const score = Math.round(c.score * 100);
    failed ||= score < TARGET;
    console.log(`${String(score).padStart(4)}  ${c.title}${score < TARGET ? "  (below 90)" : ""}`);
  }
  for (const id of ["first-contentful-paint", "largest-contentful-paint", "total-blocking-time", "cumulative-layout-shift"]) {
    console.log(`      ${audits[id].title}: ${audits[id].displayValue}`);
  }
  process.exitCode = failed ? 1 : 0;
} finally {
  await chrome.kill();
}
