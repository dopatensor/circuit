// Fails if the JavaScript loaded on first visit is over budget (gzipped). That is the
// entry script plus everything index.html preloads; lazy screens don't count.
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const BUDGET_KB = 200;
const html = readFileSync("dist/index.html", "utf8");
const files = [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+\.js)"/g)].map((m) => m[1]);
let total = 0;
for (const file of new Set(files)) {
  const kb = gzipSync(readFileSync(`dist${file}`)).length / 1024;
  total += kb;
  console.log(`${kb.toFixed(1).padStart(7)} KB  ${file}`);
}
console.log(`${total.toFixed(1).padStart(7)} KB  initial JavaScript, gzipped (budget ${BUDGET_KB} KB)`);
if (total > BUDGET_KB) {
  console.error("Over budget: lazy-load something.");
  process.exit(1);
}
