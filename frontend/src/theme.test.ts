// @vitest-environment node
//
// Questo file non tocca il DOM: legge index.css e fa aritmetica. In jsdom (l'ambiente
// di default del progetto) il costruttore globale `URL` risolve un percorso relativo
// contro `window.location` (http://localhost/) e ignora la base `file://` passata come
// secondo argomento — `fileURLToPath` riceve quindi un URL `http:` e lancia. L'ambiente
// Node usa l'`URL` di Node, che rispetta la base, com'è scritto qui sotto.
//
// `tsconfig.app.json` (che compila `src`) non porta i tipi di Node — solo
// `tsconfig.node.json` li ha, e copre vite.config.ts/e2e, non `src`. Questo file sta
// in `src` per leggere `./index.css` come gli altri moduli dell'app, quindi i tipi si
// chiedono qui, per questo solo file, invece di darli a tutto `src`.
/// <reference types="node" />
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Il contrasto dei token si controlla sui valori scritti in index.css, in chiaro e in
// scuro, senza aspettare un browser: è aritmetica. Che quei valori arrivino davvero a
// video lo misura e2e/style.spec.ts; qui si impedisce che un token nuovo, o un ritocco,
// scenda sotto 4,5:1 senza che nessuno se ne accorga.
const css = readFileSync(fileURLToPath(new URL("./index.css", import.meta.url)), "utf8");

function tokens(block: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [, name, hex] of block.matchAll(/--color-([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    out[name] = hex;
  }
  return out;
}

const light = tokens(css.match(/@theme\s*\{([\s\S]*?)\n\}/)?.[1] ?? "");
const dark = tokens(
  css.match(/@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([\s\S]*?)\}\s*\}/)?.[1] ?? ""
);

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const s = parseInt(hex.slice(i, i + 2), 16) / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

// [testo, fondo]: ogni coppia che l'app mette a video. Chi aggiunge un token che porta
// testo aggiunge qui la sua coppia.
const PAIRS: [string, string][] = [
  ["ink", "page"], ["ink", "card"],
  ["ink-soft", "page"], ["ink-soft", "card"],
  ["ink-faint", "page"], ["ink-faint", "card"],
  ["brand", "page"], ["brand", "card"], ["brand", "brand-tint"], ["on-brand", "brand"],
  ["low", "page"], ["low", "card"], ["low", "low-tint"], ["on-low", "low"],
  ["finished", "page"], ["finished", "card"], ["finished", "finished-tint"], ["on-finished", "finished"],
  ["danger", "page"], ["danger", "card"],
  ["expiry", "page"], ["expiry", "card"], ["expiry", "expiry-tint"], ["on-expiry", "expiry"],
  // l'avviso di conferma è rovesciato: fondo `ink`, testo `page`, azione `brand-tint`
  ["page", "ink"], ["brand-tint", "ink"],
  ["dept-peach-ink", "dept-peach"], ["dept-pink-ink", "dept-pink"], ["dept-blue-ink", "dept-blue"],
  ["dept-sand-ink", "dept-sand"], ["dept-slate-ink", "dept-slate"],
  // il pulsante spento, di ogni variante con un fondo pieno (bozza del tema scuro, §5 A)
  ["on-disabled", "disabled"],
];

// [segno, fondo]: le coppie di un segno che non si legge ma identifica un controllo
// (WCAG 1.4.11): la soglia è 3:1, non 4,5:1. La tacca spenta di `StockGauge` è la
// ragione per cui c'è: a 1,3:1 (`line` su `card`) le tacche non si capivano toccabili,
// che è il rischio più grosso della spec T3 (§7).
const MARK_PAIRS: [string, string][] = [
  ["notch-off", "card"],
  // il ripiego della figura di una riga in Dispensa (S12): l'icona del reparto in
  // `ink-faint` sul quadratino `page`. Come testo sta già sopra 4,5:1 (PAIRS); qui si
  // dice che per lei la soglia è quella di un segno
  ["ink-faint", "page"],
];

// [fondo, fondo]: un controllo pieno che non deve sparire contro quel che ha intorno, ma
// nemmeno dire «qui si tocca» come un segno a 3:1. È il grigio del pulsante spento: la
// soglia di 1,2:1 è quella della bozza del tema scuro (2026-10-06, §5 A), che misura
// 1,22–1,45:1 contro pagina e scheda.
const SHAPE_PAIRS: [string, string][] = [
  ["disabled", "page"],
  ["disabled", "card"],
];

// Il blocco scuro di index.css, come lo legge `dark` più sopra: serve anche al velo.
const DARK_BLOCK = /@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([\s\S]*?)\}\s*\}/;

// L'alfa del velo del ☰ (`--scrim-alpha`, in percento) in un pezzo di index.css.
function scrimAlpha(block: string): number | undefined {
  const percent = block.match(/--scrim-alpha:\s*(\d+(?:\.\d+)?)%\s*;/)?.[1];
  return percent === undefined ? undefined : Number(percent) / 100;
}

const lightScrim = scrimAlpha(css.replace(DARK_BLOCK, ""));
const darkScrim = scrimAlpha(css.match(DARK_BLOCK)?.[1] ?? "");

// Un colore con alfa sopra un fondo pieno, come lo compone il browser per il velo
// (`color-mix(…, transparent)` è `scrim` con quell'alfa): in sRGB non lineare, canale per
// canale, arrotondato a 8 bit — il metodo del §3 della bozza del tema scuro.
function mix(top: string, bottom: string, alpha: number): string {
  const channel = (hex: string, i: number) => parseInt(hex.slice(i, i + 2), 16);
  return (
    "#" +
    [1, 3, 5]
      .map((i) => Math.round(alpha * channel(top, i) + (1 - alpha) * channel(bottom, i)))
      .map((v) => v.toString(16).padStart(2, "0"))
      .join("")
  );
}

// La tacca accesa di `StockGauge` mentre una scrittura è in volo: grigia come un
// pulsante spento (`on-disabled`), non sbiadita con l'opacità (pulizie del 2026-10-13).
// Contro la scheda è un segno (3:1, WCAG 1.4.11); contro la tacca spenta (`notch-off`)
// deve dire ancora il livello: 2:1, misurato 2,13 in chiaro e 2,57 in scuro.
const OFF_GAUGE_PAIRS: [string, string, number][] = [
  ["on-disabled", "card", 3],
  ["on-disabled", "notch-off", 2],
];

describe("i token del colore", () => {
  it("ogni token chiaro ha il suo valore scuro, e viceversa", () => {
    expect(Object.keys(dark).sort()).toEqual(Object.keys(light).sort());
  });

  for (const [mode, palette] of [["chiaro", light], ["scuro", dark]] as const) {
    it.each(PAIRS)(`in ${mode}, %s su %s sta sopra 4,5:1`, (text, background) => {
      expect(palette[text], `--color-${text} manca in ${mode}`).toBeDefined();
      expect(palette[background], `--color-${background} manca in ${mode}`).toBeDefined();
      expect(ratio(palette[text], palette[background])).toBeGreaterThanOrEqual(4.5);
    });

    it.each(MARK_PAIRS)(`in ${mode}, il segno %s su %s sta sopra 3:1`, (mark, background) => {
      expect(palette[mark], `--color-${mark} manca in ${mode}`).toBeDefined();
      expect(palette[background], `--color-${background} manca in ${mode}`).toBeDefined();
      expect(ratio(palette[mark], palette[background])).toBeGreaterThanOrEqual(3);
    });

    it.each(SHAPE_PAIRS)(`in ${mode}, la forma %s su %s non sparisce: sopra 1,2:1`, (shape, background) => {
      expect(palette[shape], `--color-${shape} manca in ${mode}`).toBeDefined();
      expect(palette[background], `--color-${background} manca in ${mode}`).toBeDefined();
      expect(ratio(palette[shape], palette[background])).toBeGreaterThanOrEqual(1.2);
    });

    it.each(OFF_GAUGE_PAIRS)(
      `in ${mode}, la tacca spenta accesa %s contro %s sta sopra %s:1`,
      (mark, background, min) => {
        expect(palette[mark], `--color-${mark} manca in ${mode}`).toBeDefined();
        expect(palette[background], `--color-${background} manca in ${mode}`).toBeDefined();
        expect(ratio(palette[mark], palette[background])).toBeGreaterThanOrEqual(min);
      }
    );
  }
});

// Il velo del ☰ (bozza del tema scuro, §6, V1 + V2): `scrim` con l'alfa del tema sopra
// la pagina. In scuro la pagina è già quasi nera e il velo non ha dove scendere: il
// pannello `card` resta a 1,2:1 da ciò che copre, e a staccarlo è il bordo `panel-edge`.
// In chiaro il bordo vale quanto `card` e a staccarlo è il bianco del pannello. La
// soglia è quella di un segno (3:1), per il pannello o per il suo bordo.
describe("il velo del ☰", () => {
  it("l'alfa del velo è scritta per tutti e due i temi, fra 0 e 1", () => {
    for (const alpha of [lightScrim, darkScrim]) {
      expect(alpha).toBeDefined();
      expect(alpha!).toBeGreaterThan(0);
      expect(alpha!).toBeLessThan(1);
    }
  });

  it("l'alfa chiara sta prima del blocco scuro: dopo, a parità di `:root`, vincerebbe anche in scuro", () => {
    const lightAt = css.search(/--scrim-alpha:/);
    const darkBlockAt = css.search(/@media \(prefers-color-scheme: dark\)/);
    expect(lightAt).toBeGreaterThanOrEqual(0);
    expect(lightAt).toBeLessThan(darkBlockAt);
  });

  for (const [mode, palette, alpha] of [
    ["chiaro", light, lightScrim],
    ["scuro", dark, darkScrim],
  ] as const) {
    it.each(["page", "card"])(
      `in ${mode}, il pannello si stacca da %s velata: lui o il suo bordo sopra 3:1`,
      (under) => {
        expect(alpha, `--scrim-alpha manca in ${mode}`).toBeDefined();
        for (const token of ["card", "panel-edge", "scrim", under]) {
          expect(palette[token], `--color-${token} manca in ${mode}`).toBeDefined();
        }
        const veiled = mix(palette.scrim, palette[under], alpha!);
        expect(
          Math.max(ratio(palette.card, veiled), ratio(palette["panel-edge"], veiled))
        ).toBeGreaterThanOrEqual(3);
      }
    );
  }
});
