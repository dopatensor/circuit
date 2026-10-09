// Generates the app icons: the Circuit mark (three people on a teal loop) on the
// off-white background. Renders an SVG with Playwright's Chromium and screenshots it,
// so no image tools are needed. Run once (npm run icons) and commit the files in public/.
import { chromium } from "@playwright/test";
import { writeFileSync } from "node:fs";

const BG = "#fbfaf8";
const SIGNAL = "#0a6b82";
// The mark on a 24-unit grid, the same drawing as <Logo> in src/components/ds/Icon.tsx.
const mark = (stroke) =>
  `<circle cx="12" cy="12" r="8" fill="none" stroke="${SIGNAL}" stroke-width="${stroke}"/>` +
  [[12, 4], [5.1, 16], [18.9, 16]]
    .map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2.4" fill="${BG}" stroke="${SIGNAL}" stroke-width="${stroke}"/>`)
    .join("");
const svg = (scale) => {
  // scale: how much of the icon the mark fills (maskable icons keep to the middle 80%).
  const pad = (24 / scale - 24) / 2;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${-pad} ${-pad} ${24 + 2 * pad} ${24 + 2 * pad}">` +
    `<rect x="${-pad}" y="${-pad}" width="${24 + 2 * pad}" height="${24 + 2 * pad}" fill="${BG}"/>${mark(1.8)}</svg>`;
};

const icons = [
  { file: "pwa-192.png", size: 192, scale: 0.72 },
  { file: "pwa-512.png", size: 512, scale: 0.72 },
  { file: "maskable-512.png", size: 512, scale: 0.52 },
  { file: "apple-touch-icon.png", size: 180, scale: 0.68 },
];

const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 1 });
for (const { file, size, scale } of icons) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<!doctype html><body style="margin:0">${svg(scale).replace("<svg ", `<svg width="${size}" height="${size}" `)}</body>`);
  await page.screenshot({ path: `public/${file}` });
  console.log(`public/${file}`);
}
await browser.close();

writeFileSync("public/favicon.svg", `${svg(0.86)}\n`);
console.log("public/favicon.svg");
