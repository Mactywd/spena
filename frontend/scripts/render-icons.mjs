// Rigenera le icone PNG della PWA dal favicon SVG, così il verde del marchio è uno
// solo. Si lancia a mano quando cambia il marchio: `node scripts/render-icons.mjs`.
// Usa il Chromium di Playwright, che il progetto ha già: nessuna dipendenza nuova.
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const svg = readFileSync(new URL("../public/favicon.svg", import.meta.url), "utf8");
const browser = await chromium.launch();
for (const size of [192, 512]) {
  const page = await browser.newPage({ viewport: { width: size, height: size } });
  await page.setContent(
    `<html><body style="margin:0">${svg.replace(/width="512" height="512"/, `width="${size}" height="${size}"`)}</body></html>`
  );
  await page.screenshot({
    path: new URL(`../public/icon-${size}.png`, import.meta.url).pathname,
    omitBackground: true,
  });
  await page.close();
}
await browser.close();
