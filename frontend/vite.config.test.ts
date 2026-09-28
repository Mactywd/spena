// @vitest-environment node
import { readFileSync } from "node:fs";
import { matchesGlob } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { PRECACHE_GLOB_PATTERNS } from "./vite.config.ts";

// Inter è servito dall'app proprio perché la PWA funzioni senza rete (spec T3 §2):
// un carattere che il service worker non mette da parte arriva dalla rete o non
// arriva, e offline il testo ripiega sul carattere di sistema. La prima stesura non
// lo precaricava affatto: gli schemi di default di Workbox sono `**/*.{js,css,html}`.
//
// Qui si provano gli schemi veri, quelli che vite.config.ts passa a Workbox, contro i
// nomi che la costruzione produce: i file di Fontsource elencati dal suo CSS, col
// suffisso di hash che Vite aggiunge (`assets/[name]-[hash][extname]`). Il `sw.js`
// costruito lo legge l'e2e (`style.spec.ts`), servito da Nginx: questo è il controllo
// veloce, quello è la prova sull'app che gira.
const precached = (file: string) => PRECACHE_GLOB_PATTERNS.some((pattern) => matchesGlob(file, pattern));

const interCss = readFileSync(
  fileURLToPath(new URL("./node_modules/@fontsource-variable/inter/index.css", import.meta.url)),
  "utf8"
);
// i file che l'import in main.tsx porta davvero nella costruzione, un sottoinsieme per
// alfabeto; l'hash è finto ma della stessa forma, trattini e sottolineati compresi
const builtFonts = [...interCss.matchAll(/url\(\.\/files\/([\w-]+)\.woff2\)/g)].map(
  ([, name]) => `assets/${name}-Dx_4k-Al.woff2`
);

describe("il precaricamento del service worker", () => {
  it("tiene Inter latino e latino esteso: sono le lettere dell'italiano", () => {
    const latin = builtFonts.filter((file) => /inter-latin(-ext)?-wght-normal-/.test(file));
    expect(latin).toHaveLength(2);
    for (const file of latin) expect(precached(file), file).toBe(true);
  });

  it("lascia fuori gli altri alfabeti: si scaricano per unicode-range solo se servono", () => {
    const others = builtFonts.filter((file) => !/inter-latin(-ext)?-wght-normal-/.test(file));
    // cirillico, cirillico esteso, greco, greco esteso, vietnamita: se Fontsource ne
    // togliesse uno il conto cambia, e va riguardato
    expect(others.length).toBeGreaterThanOrEqual(5);
    for (const file of others) expect(precached(file), file).toBe(false);
  });

  it("tiene ancora quel che teneva prima: la pagina, il codice e lo stile", () => {
    for (const file of ["index.html", "registerSW.js", "assets/index-CS2wZeP1.js", "assets/index-D6tZZaDM.css"]) {
      expect(precached(file), file).toBe(true);
    }
  });
});
