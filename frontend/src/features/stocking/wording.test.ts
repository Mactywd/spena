import { describe, expect, it } from "vitest";
import { elsewhereNote, otherIngredient } from "./wording";

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
