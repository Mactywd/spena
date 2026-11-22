import { describe, expect, it } from "vitest";
import { elsewhereNote, newCodeNote, otherIngredient } from "./wording";

describe("otherIngredient", () => {
  it("dice quale ingrediente, non solo che è un altro", () => {
    expect(otherIngredient("Parmigiano Reggiano 24 mesi", "burro")).toBe(
      "«Parmigiano Reggiano 24 mesi» è di un altro ingrediente: burro."
    );
  });
});

describe("elsewhereNote", () => {
  it.each([
    [["burro"], "Un altro prodotto corrisponde, ma è di un altro ingrediente: burro."],
    [["burro", "burro"], "Altri 2 prodotti corrispondono, ma sono di un altro ingrediente: burro."],
    [
      ["burro", "latte", "burro"],
      "Altri 3 prodotti corrispondono, ma sono di altri ingredienti: burro, latte.",
    ],
  ] as const)("%j → «%s»", (names, text) => {
    expect(elsewhereNote([...names])).toBe(text);
  });
});

describe("newCodeNote", () => {
  const CODE = "8001234567890";

  it("con un suggerimento, dice cosa ne sa Open Food Facts", () => {
    const suggestion = {
      name: "Lenticchie rosse", brand: "Coop", barcode: CODE, nutrients: {}, image_url: null,
    };
    expect(newCodeNote(CODE, suggestion)).toBe("Su Open Food Facts è «Lenticchie rosse», di Coop.");
  });

  it("senza codice, dice cosa resta da fare", () => {
    expect(newCodeNote("", null)).toBe(
      "Nessun codice a barre: scegli l'ingrediente, poi scrivi il prodotto."
    );
  });

  it("un lookup fallito non è un «non trovato»: non l'ha cercato nessuno", () => {
    expect(newCodeNote(CODE, null, "failed")).toBe(
      `Non ho potuto cercare il codice ${CODE}: scegli l'ingrediente, poi scrivi il prodotto.`
    );
  });

  it("un codice che nessuno conosce", () => {
    expect(newCodeNote(CODE, null, "not_found")).toBe(
      `Il codice ${CODE} non è in catalogo né su Open Food Facts.`
    );
  });
});
