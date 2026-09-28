import { describe, expect, it } from "vitest";
import { entryNote, groupForDisplay } from "./listView";
import type { ShoppingItem } from "../../domain/types";

function item(id: string, category: string | null, status: ShoppingItem["status"] = "pending"): ShoppingItem {
  return {
    id, raw_text: id, ingredient_id: category ? `i-${id}` : null, ingredient_name: category ? id : null,
    ingredient_category: category, ingredient_kind: category ? "food" : null, status,
    reason: "manual", created_at: "2026-09-28T10:00:00Z",
  };
}

const ids = (groups: [string | null, ShoppingItem[]][]) =>
  groups.map(([category, rows]) => [category, rows.map((row) => row.id)]);

describe("groupForDisplay", () => {
  it("i reparti in ordine alfabetico, quello ignoto in fondo", () => {
    const groups = groupForDisplay([item("a", "verdura"), item("b", null), item("c", "bevande")]);
    expect(ids(groups)).toEqual([["bevande", ["c"]], ["verdura", ["a"]], [null, ["b"]]]);
  });

  it("dentro il reparto le voci nel carrello vanno in fondo (dal giro)", () => {
    const groups = groupForDisplay([
      item("uova", "latticini", "checked"),
      item("latte", "latticini"),
      item("burro", "latticini", "checked"),
      item("yogurt", "latticini"),
    ]);
    // prima le da comprare, poi le spuntate; ciascun gruppo nell'ordine d'arrivo
    expect(ids(groups)).toEqual([["latticini", ["latte", "yogurt", "uova", "burro"]]]);
  });

  it("il reparto ignoto segue la stessa regola", () => {
    const groups = groupForDisplay([item("x", null, "checked"), item("y", null)]);
    expect(ids(groups)).toEqual([[null, ["y", "x"]]]);
  });

  it("una lista vuota non ha reparti", () => {
    expect(groupForDisplay([])).toEqual([]);
  });

  it("non tocca l'array che riceve: è la cache di React Query", () => {
    const input = [item("b", "latticini", "checked"), item("a", "latticini")];
    groupForDisplay(input);
    expect(input.map((row) => row.id)).toEqual(["b", "a"]);
  });
});

describe("entryNote", () => {
  it.each([
    [null, "Metti via quello che hai comprato"],
    [0, "Niente nel carrello, per ora"],
    [1, "1 nel carrello"],
    [7, "7 nel carrello"],
  ] as const)("%s → %s", (inCart, note) => {
    expect(entryNote(inCart)).toBe(note);
  });
});
