import { describe, expect, it } from "vitest";
import { readVariantState, variantPath } from "./variantState";
import type { RecipeDraft } from "../../domain/types";

const DRAFT: RecipeDraft = {
  title: "Torta di mele con dolcificante", description: null, instructions: "1. Impasta.",
  servings: 8, cost: 2, ingredients: [],
};

describe("readVariantState", () => {
  it("legge la proposta portata dalla cronologia", () => {
    const state = {
      prompt: "con dolcificante", draft: DRAFT, originTitle: "Torta di mele", originCategory: "Dolci",
    };
    expect(readVariantState(state)).toEqual(state);
  });

  it.each([
    [null],
    [undefined],
    ["testo"],
    [{}],
    [{ prompt: "x", originTitle: "y" }],
    [{ prompt: "x", originTitle: "y", draft: { title: "z" } }],
  ])("una voce della cronologia senza proposta (%j) non è una variante", (state) => {
    expect(readVariantState(state)).toBeNull();
  });

  it("una categoria assente vale «nessuna»", () => {
    expect(readVariantState({ prompt: "x", draft: DRAFT, originTitle: "y" })?.originCategory).toBeNull();
  });
});

describe("variantPath", () => {
  it("la variante si corregge sotto la ricetta da cui nasce", () => {
    expect(variantPath("r1")).toBe("/ricette/r1/variante");
  });
});
