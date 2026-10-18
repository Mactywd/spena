// @vitest-environment node
//
// Legge i sorgenti dei test, non tocca il DOM: in ambiente `node` per lo stesso motivo di
// theme.test.ts (l'`URL` di jsdom ignora la base `file://`), coi tipi di Node chiesti qui.
/// <reference types="node" />
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC = fileURLToPath(new URL("..", import.meta.url));
const SELF = fileURLToPath(import.meta.url);

function tests(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return tests(path);
    return /\.test\.tsx?$/.test(name) && path !== SELF ? [path] : [];
  });
}

// Prima lezione di CLAUDE.md: un test che si costruisce il suo oggetto non prova quello
// che gira. Ogni test di schermata prende il client da `createTestQueryClient`, che è
// quello dell'app; un `new QueryClient(` qui vorrebbe dire un client che la produzione
// non ha (pulizie del 2026-10-13).
describe("i test di schermata", () => {
  it("nessuno si costruisce il client react-query a mano", () => {
    const found = tests(SRC).filter((file) => readFileSync(file, "utf8").includes("new QueryClient("));
    expect(found.map((file) => file.slice(SRC.length))).toEqual([]);
  });
});
