// Generates the app icons: a plain "C" in the system font, black on white.
// Renders HTML with Playwright's Chromium and screenshots it, so no image tools are
// needed. Run once (npm run icons) and commit the PNGs in public/.
import { chromium } from "@playwright/test";
import { writeFileSync } from "node:fs";

const FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif";

// maskable: Android may crop to a circle, so the letter stays inside the middle 80%.
const icons = [
  { file: "pwa-192.png", size: 192, scale: 0.62 },
  { file: "pwa-512.png", size: 512, scale: 0.62 },
  { file: "maskable-512.png", size: 512, scale: 0.46 },
  { file: "apple-touch-icon.png", size: 180, scale: 0.62 },
];

const html = (size, scale) => `<!doctype html><html><body style="margin:0">
  <div style="width:${size}px;height:${size}px;background:#0a0a0a;color:#fff;display:flex;
    align-items:center;justify-content:center;font:600 ${Math.round(size * scale)}px/1 ${FONT};
    letter-spacing:-0.02em">C</div></body></html>`;

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 1 });
for (const { file, size, scale } of icons) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(html(size, scale));
  await page.screenshot({ path: `public/${file}`, omitBackground: false });
  console.log(`public/${file}`);
}
await browser.close();

// Vector favicon for browsers that take SVG.
writeFileSync(
  "public/favicon.svg",
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#0a0a0a"/>` +
    `<text x="32" y="45" text-anchor="middle" font-family="system-ui, sans-serif" font-size="40" font-weight="600" fill="#fff">C</text></svg>\n`,
);
console.log("public/favicon.svg");
