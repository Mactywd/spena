import { describe, expect, it } from "vitest";
import { entryLabel, entryTitle, type EntryChoice } from "./entryView";
import type { Product } from "../../domain/types";

const YOGURT = { id: "i1", name: "yogurt greco", kind: "food" } as const;
const FAGE: Product = {
  id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};

describe("entryTitle ed entryLabel", () => {
  it("un prodotto: il titolo è il suo nome, l'avviso mette la marca davanti, come sulla confezione", () => {
    const choice: EntryChoice = { ingredient: YOGURT, product: FAGE };
    expect(entryTitle(choice)).toBe("Total 0%");
    expect(entryLabel(choice)).toBe("Fage Total 0%");
    expect(entryLabel({ ingredient: YOGURT, product: { ...FAGE, brand: null } })).toBe("Total 0%");
  });

  it("uno sfuso: l'ingrediente con la maiuscola, solo a video", () => {
    const choice: EntryChoice = { ingredient: YOGURT, product: null };
    expect(entryTitle(choice)).toBe("Yogurt greco");
    expect(entryLabel(choice)).toBe("Yogurt greco");
  });
});
