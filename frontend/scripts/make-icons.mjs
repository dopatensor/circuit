// Generates the app icons: the Circuit logo (the traced "C" with a lime and a blue
// terminal and an orange chip) on pitch black. Renders an SVG with Playwright's
// Chromium and screenshots it, so no image tools are needed. Run once (npm run icons)
// and commit the files in public/.
import { chromium } from "@playwright/test";
import { writeFileSync } from "node:fs";

const BG = "#000000";
// The logo on its 1600-unit grid, the same drawing as <Logo> in src/components/ds/Icon.tsx.
// The content spans x 112..1312 and y 112..1488, so its centre is (712, 800).
const C =
  "M112 388L388 112H1012L1200 300V470H842L644 668V862H556V632L806 382H1032L938 288H462L288 462V1138" +
  "L462 1312H938L1125 1125L1250 1250L1012 1488H388L112 1212Z";
const mark =
  `<mask id="cut"><rect x="-2000" y="-2000" width="6000" height="6000" fill="white"/>` +
  `<circle cx="1200" cy="425" r="150" fill="black"/><circle cx="1200" cy="1175" r="150" fill="black"/></mask>` +
  `<path d="${C}" fill="#F4F4F0" mask="url(#cut)"/>` +
  `<rect x="500" y="900" width="200" height="200" fill="#FF4F00"/>` +
  `<circle cx="1200" cy="425" r="88" fill="none" stroke="#CCFF00" stroke-width="49"/>` +
  `<circle cx="1200" cy="425" r="25" fill="#CCFF00"/>` +
  `<circle cx="1200" cy="1175" r="88" fill="none" stroke="#3B82F6" stroke-width="49"/>` +
  `<circle cx="1200" cy="1175" r="25" fill="#3B82F6"/>`;
const svg = (scale) => {
  // scale: how much of the icon the logo's height fills (maskable icons keep to the middle 80%).
  const side = 1376 / scale;
  const x = 712 - side / 2;
  const y = 800 - side / 2;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${x} ${y} ${side} ${side}">` +
    `<rect x="${x}" y="${y}" width="${side}" height="${side}" fill="${BG}"/>${mark}</svg>`;
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
