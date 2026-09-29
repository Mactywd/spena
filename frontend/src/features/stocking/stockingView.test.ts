import { describe, expect, it } from "vitest";
import { stockEntries, stockNotice, type Resolution } from "./stockingView";
import type { Product, ShoppingItem } from "../../domain/types";

function item(id: string, ingredientId: string | null): ShoppingItem {
  return {
    id, raw_text: id, ingredient_id: ingredientId, ingredient_name: ingredientId ? id : null,
    ingredient_category: ingredientId ? "altro" : null, ingredient_kind: ingredientId ? "food" : null,
    status: "checked", reason: "manual", created_at: "2026-09-29T10:00:00Z",
  };
}

const FAGE: Product = {
  id: "p1", ingredient_id: "i-yogurt", ingredient_name: "yogurt greco", name: "Total 0%",
  brand: "Fage", barcode: "5201054000138", source: "openfoodfacts", nutrients: null, image_url: null,
};

const ownIngredient = (row: ShoppingItem) => row.ingredient_id;
const ids = (entries: { shopping_item_id: string }[]) => entries.map((entry) => entry.shopping_item_id);

describe("stockEntries", () => {
  it("una voce sfusa parte senza prodotto e senza codice", () => {
    expect(stockEntries([item("s1", "i1")], { s1: { kind: "loose" } }, ownIngredient, {})).toEqual([
      { shopping_item_id: "s1", ingredient_id: "i1", product_id: null, expires_on: null, barcode: null },
    ]);
  });

  it("un prodotto porta il suo id, e il codice letto solo se c'è (S8)", () => {
    const resolved: Record<string, Resolution> = {
      s1: { kind: "product", product: FAGE, barcode: "8001234567890" },
      s2: { kind: "product", product: FAGE },
    };
    expect(stockEntries([item("s1", "i1"), item("s2", "i2")], resolved, ownIngredient, {})).toEqual([
      { shopping_item_id: "s1", ingredient_id: "i1", product_id: "p1", expires_on: null,
        barcode: "8001234567890" },
      { shopping_item_id: "s2", ingredient_id: "i2", product_id: "p1", expires_on: null,
        barcode: null },
    ]);
  });

  it("parte solo chi ha una scelta e un ingrediente", () => {
    const entries = stockEntries(
      [item("scelta", "i1"), item("senza-scelta", "i2"), item("senza-ingrediente", null)],
      { scelta: { kind: "loose" }, "senza-ingrediente": { kind: "loose" } },
      ownIngredient,
      {}
    );
    expect(ids(entries)).toEqual(["scelta"]);
  });

  it("l'ingrediente abbinato qui vale quanto quello della lista (S19)", () => {
    const matched = (row: ShoppingItem) => row.ingredient_id ?? "i-abbinato";
    const [entry] = stockEntries([item("s3", null)], { s3: { kind: "loose" } }, matched, {});
    expect(entry.ingredient_id).toBe("i-abbinato");
  });

  it("la scelta di una voce che non c'è più non parte: decide la lista riletta", () => {
    const resolved: Record<string, Resolution> = { s1: { kind: "loose" }, sparita: { kind: "loose" } };
    expect(ids(stockEntries([item("s1", "i1")], resolved, ownIngredient, {}))).toEqual(["s1"]);
  });

  it("nell'ordine della lista, non in quello delle scelte", () => {
    const resolved: Record<string, Resolution> = { s2: { kind: "loose" }, s1: { kind: "loose" } };
    expect(ids(stockEntries([item("s1", "i1"), item("s2", "i2")], resolved, ownIngredient, {})))
      .toEqual(["s1", "s2"]);
  });

  // `||` e non `??`: un campo data svuotato lascia "", che non è una data — il backend
  // risponderebbe 422, e riprovare rimanderebbe lo stesso corpo per sempre
  it.each([
    ["mai scritta", undefined, null],
    ["scritta e poi svuotata", "", null],
    ["scritta", "2026-10-02", "2026-10-02"],
  ] as const)("la scadenza %s parte come %s", (_caso, written, sent) => {
    const expiry: Record<string, string> = written === undefined ? {} : { s1: written };
    const [entry] = stockEntries([item("s1", "i1")], { s1: { kind: "loose" } }, ownIngredient, expiry);
    expect(entry.expires_on).toBe(sent);
  });
});

describe("stockNotice", () => {
  it.each([
    [4, 7, "4 in dispensa · 3 restano in lista"],
    [4, 4, "4 in dispensa"],
    [1, 1, "1 in dispensa"],
    [1, 2, "1 in dispensa · 1 resta in lista"],
    [2, 5, "2 in dispensa · 3 restano in lista"],
  ] as const)("%i mandate su %i nel carrello → «%s»", (sent, checked, text) => {
    expect(stockNotice(sent, checked)).toBe(text);
  });
});
