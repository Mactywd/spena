// @vitest-environment node
//
// Questo file non tocca il DOM: legge i sorgenti di `src`. In ambiente `node` per lo
// stesso motivo di theme.test.ts (l'`URL` di jsdom ignora la base `file://`), e coi tipi
// di Node chiesti qui, per questo file solo.
/// <reference types="node" />
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC = fileURLToPath(new URL(".", import.meta.url));

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) ? [path] : [];
  });
}

// Lo spento non sbiadisce (tema scuro, 2026-10-07; esteso a tutti i controlli il
// 2026-10-13): un'`opacity` compone colore e fondo con quel che c'è dietro, e in chiaro
// portava il testo spento a 1,8:1. Un fondo pieno spento è il grigio `disabled`, un testo
// spento è `ink-faint`. La prova guarda il sorgente e non il CSS: l'e2e salta il testo
// sotto un'opacità, e un controllo nuovo che sbiadisce non lo vedrebbe nessuno.
describe("lo spento", () => {
  it("nessun controllo si spegne con l'opacità", () => {
    const found: string[] = [];
    for (const file of sources(SRC)) {
      readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, index) => {
          if (/(?:^|[\s"'`])(?:aria-)?disabled:opacity-/.test(line)) {
            found.push(`${file.slice(SRC.length)}:${index + 1}`);
          }
        });
    }
    expect(found).toEqual([]);
  });
});
