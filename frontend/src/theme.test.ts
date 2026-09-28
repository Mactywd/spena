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
  }
});
