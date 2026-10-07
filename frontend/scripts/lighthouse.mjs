// Lighthouse scores for the built app, as a phone on a slow network sees it
// (Lighthouse's default mobile profile: a mid-range Android, simulated slow 4G).
//
//   npm run build && npx vite preview --port 4183 &   (API on :8000, DEMO_AUTH=true)
//   npm run lighthouse -- http://localhost:4183/welcome
//   npm run lighthouse -- http://localhost:4183/map --as ravi      (signed in first)
//   add --details to list the audits that cost points
//
// Uses Playwright's Chromium. Note: Lighthouse 12+ dropped its "PWA" category;
// installability is checked by e2e/pwa.spec.ts instead.
import { chromium } from "@playwright/test";
import lighthouse from "lighthouse";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const args = process.argv.slice(2);
const url = args.find((a) => a.startsWith("http")) ?? "http://localhost:4183/welcome";
const asIndex = args.indexOf("--as");
const persona = asIndex >= 0 ? args[asIndex + 1] : null;
const TARGET = 90;
const PORT = 9333;

// One browser profile shared by the sign-in step and Lighthouse.
const profile = mkdtempSync(join(tmpdir(), "circuit-lh-"));
const browser = await chromium.launchPersistentContext(profile, {
  headless: true,
  args: [`--remote-debugging-port=${PORT}`],
});
try {
  if (persona) {
    const page = await browser.newPage();
    await page.goto(new URL("/welcome", url).href);
    const ok = await page.evaluate(async (key) => {
      const r = await fetch("/api/auth/demo/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona: key }),
      });
      if (!r.ok) return false;
      const out = await r.json();
      localStorage.setItem("circuit.token", out.access_token);
      localStorage.setItem("circuit.member", JSON.stringify({ member: out.member, isDemo: true }));
      return true;
    }, persona);
    if (!ok) throw new Error(`Couldn't sign in as ${persona} (is DEMO_AUTH on?)`);
    await page.close();
  }
  const result = await lighthouse(url, {
    port: PORT,
    output: "json",
    logLevel: "error",
    disableStorageReset: true, // keep the sign-in
    onlyCategories: ["performance", "accessibility", "best-practices", "seo"],
  });
  const { categories, audits } = result.lhr;
  let failed = false;
  console.log(`Lighthouse (mobile, slow 4G) for ${url}${persona ? ` as ${persona}` : ""}`);
  for (const c of Object.values(categories)) {
    const score = Math.round(c.score * 100);
    failed ||= score < TARGET;
    console.log(`${String(score).padStart(4)}  ${c.title}${score < TARGET ? "  (below 90)" : ""}`);
  }
  for (const id of ["first-contentful-paint", "largest-contentful-paint", "total-blocking-time", "cumulative-layout-shift"]) {
    console.log(`      ${audits[id].title}: ${audits[id].displayValue}`);
  }
  if (args.includes("--details")) {
    for (const [id, c] of Object.entries(categories)) {
      for (const ref of c.auditRefs) {
        const a = audits[ref.id];
        if (ref.weight > 0 && a.score !== null && a.score < 0.9) {
          console.log(`  - ${id}: ${a.title}${a.displayValue ? ` (${a.displayValue})` : ""}`);
        }
      }
    }
  }
  process.exitCode = failed ? 1 : 0;
} finally {
  await browser.close();
  rmSync(profile, { recursive: true, force: true });
}
