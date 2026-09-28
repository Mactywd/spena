import { describe, expect, it } from "vitest";
import type { PantryItem } from "../../domain/types";
import {
  expiryCounts,
  expirySummary,
  groupForDisplay,
  isExpiring,
  itemLabel,
  matchesQuery,
} from "./pantryView";

function item(over: Partial<PantryItem>): PantryItem {
  return {
    id: "x",
    ingredient_id: "i",
    product_id: null,
    ingredient_name: "mela",
    ingredient_category: "frutta",
    product_name: null,
    product_brand: null,
    status: "available",
    fill_percent: null,
    note: null,
    added_at: "2026-09-11T10:00:00Z",
    expires_on: null,
    expiry: null,
    ...over,
  };
}

describe("itemLabel", () => {
  it("usa il prodotto se c'è, l'ingrediente altrimenti", () => {
    expect(itemLabel(item({ product_name: "Total 0%" }))).toBe("Total 0%");
    expect(itemLabel(item({}))).toBe("mela");
  });
});

describe("matchesQuery", () => {
  const yogurt = item({ ingredient_name: "yogurt greco", product_name: "Total 0%", product_brand: "Fage" });
  it.each([
    ["", true],
    ["   ", true],
    ["yog", true],
    ["GRECO", true],
    ["total", true],
    ["fage", true],
    ["latte", false],
  ])("«%s» → %s", (query, expected) => {
    expect(matchesQuery(yogurt, query)).toBe(expected);
  });

  it("non guarda gli accenti: «caffe» trova «caffè»", () => {
    expect(matchesQuery(item({ ingredient_name: "caffè" }), "caffe")).toBe(true);
    expect(matchesQuery(item({ ingredient_name: "caffe" }), "caffè")).toBe(true);
  });
});

describe("isExpiring", () => {
  it.each([
    [{ expiry: "soon" as const }, true],
    [{ expiry: "expired" as const }, true],
    [{ expiry: null }, false],
    // un barattolo finito non allarma: non c'è più niente da consumare in tempo
    [{ expiry: "soon" as const, status: "finished" as const }, false],
    [{ expiry: "expired" as const, status: "low" as const }, true],
  ])("%o → %s", (over, expected) => {
    expect(isExpiring(item(over))).toBe(expected);
  });
});

describe("expiryCounts ed expirySummary", () => {
  it("conta le voci per verdetto, senza le finite", () => {
    const items = [
      item({ id: "a", expiry: "soon" }),
      item({ id: "b", expiry: "soon" }),
      item({ id: "c", expiry: "expired" }),
      item({ id: "d", expiry: "soon", status: "finished" }),
      item({ id: "e" }),
    ];
    expect(expiryCounts(items)).toEqual({ soon: 2, expired: 1 });
  });

  it.each([
    [{ soon: 0, expired: 0 }, null],
    [{ soon: 1, expired: 0 }, "1 in scadenza questa settimana"],
    [{ soon: 3, expired: 0 }, "3 in scadenza questa settimana"],
    [{ soon: 0, expired: 2 }, "2 oltre la scadenza"],
    [{ soon: 2, expired: 1 }, "2 in scadenza questa settimana · 1 oltre la scadenza"],
  ])("%o → %s", (counts, expected) => {
    expect(expirySummary(counts)).toBe(expected);
  });
});

describe("groupForDisplay", () => {
  it("reparti in ordine alfabetico, e dentro l'ordine del server", () => {
    const groups = groupForDisplay([
      item({ id: "1", ingredient_category: "verdura" }),
      item({ id: "2", ingredient_category: "frutta" }),
      item({ id: "3", ingredient_category: "verdura" }),
    ]);
    expect(groups.map(([category, rows]) => [category, rows.map((r) => r.id)])).toEqual([
      ["frutta", ["2"]],
      ["verdura", ["1", "3"]],
    ]);
  });

  it("le finite vanno in fondo alla loro sezione, ciascun gruppo nel suo ordine", () => {
    const [[, rows]] = groupForDisplay([
      item({ id: "a", status: "finished" }),
      item({ id: "b" }),
      item({ id: "c", status: "finished" }),
      item({ id: "d", status: "low" }),
    ]);
    expect(rows.map((r) => r.id)).toEqual(["b", "d", "a", "c"]);
  });
});
