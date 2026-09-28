import { describe, expect, it } from "vitest";
import type { DraftIngredient, Ingredient, RecipeDetail, RecipeDraft } from "../../domain/types";
import {
  EMPTY_FORM,
  applyDraft,
  lineFromDraft,
  lineFromIngredient,
  matchNote,
  recipeBody,
  showsMatch,
  validationProblem,
  valuesFromRecipe,
} from "./formModel";

const DETAIL: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: null, source: "dataset",
  missing: 0, cookable: true, missing_names: [], image_url: null, prep_minutes: null,
  cook_minutes: null, category: "Primi piatti", cost: 2, archived_at: null,
  instructions: "Cuoci.", servings: 4, source_ref: "https://esempio.invalid/pasta",
  scaled_to: null, unscalable_lines: 0, dose_lines: 1, owned_by_import: true,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "320 g",
      quantity_display: "320 g", quantity_scaled: false, note: "al dente",
      availability: "available", satisfied: true },
    { ingredient_id: "i2", ingredient_name: "basilico", role: "secondary", quantity_text: null,
      quantity_display: null, quantity_scaled: false, note: null,
      availability: "missing", satisfied: false },
  ],
};

const ZAFFERANO: Ingredient = {
  id: "i9", name: "zafferano", display_name: "Zafferano", category: "spezie", kind: "food",
};

function bozza(overrides: Partial<DraftIngredient>): DraftIngredient {
  return {
    raw_name: "pasta", role: "primary", quantity_text: "180 g", ingredient_id: "i1",
    matched_name: "pasta", confident: true, proposed_category: null, ...overrides,
  };
}

describe("il modulo riempito da una ricetta salvata", () => {
  it("riprende i campi, la dose scritta e la nota", () => {
    const values = valuesFromRecipe(DETAIL);

    expect(values).toMatchObject({
      title: "Pasta al pomodoro", description: "", category: "Primi piatti",
      servingsText: "4", cost: 2, instructions: "Cuoci.",
    });
    expect(values.lines.map((l) => [l.label, l.role, l.quantityText, l.note, l.included])).toEqual([
      ["pasta", "primary", "320 g", "al dente", true],
      ["basilico", "secondary", "", null, true],
    ]);
  });

  it("la dose è quella scritta, non quella riscalata", () => {
    const riscalata: RecipeDetail = {
      ...DETAIL,
      ingredients: [{ ...DETAIL.ingredients[0], quantity_display: "640 g", quantity_scaled: true }],
    };
    expect(valuesFromRecipe(riscalata).lines[0].quantityText).toBe("320 g");
  });

  it("salvato senza toccare niente, torna identico, con la nota solo dove c'è", () => {
    expect(recipeBody(valuesFromRecipe(DETAIL))).toEqual({
      title: "Pasta al pomodoro", description: null, category: "Primi piatti",
      instructions: "Cuoci.", servings: 4, cost: 2,
      ingredients: [
        { ingredient_id: "i1", role: "primary", quantity_text: "320 g", note: "al dente" },
        { ingredient_id: "i2", role: "secondary", quantity_text: null },
      ],
    });
  });
});

describe("la bozza dell'AI", () => {
  const DRAFT: RecipeDraft = {
    title: "Bozza", description: "Svelta", instructions: "1. Cuoci.", servings: 2, cost: 3,
    ingredients: [bozza({})],
  };

  it("sostituisce le righe del modello e lascia quelle scelte da te, e la categoria", () => {
    const prima = {
      ...EMPTY_FORM,
      category: "Primi piatti",
      lines: [lineFromDraft(bozza({ raw_name: "vecchia" }), 0), lineFromIngredient(ZAFFERANO)],
    };

    const dopo = applyDraft(prima, DRAFT);

    expect(dopo.lines.map((l) => l.label)).toEqual(["pasta", "Zafferano"]);
    expect(dopo).toMatchObject({
      title: "Bozza", description: "Svelta", servingsText: "2", cost: 3, category: "Primi piatti",
    });
  });

  it("un aggancio incerto non confermato non parte; una riga da creare parte con nome e categoria", () => {
    const values = {
      ...EMPTY_FORM, title: "x", instructions: "y",
      lines: [
        lineFromDraft(bozza({ raw_name: "basilico fresco", ingredient_id: "i2", matched_name: "basilico", confident: false }), 0),
        lineFromDraft(bozza({ raw_name: "Speck", quantity_text: "", ingredient_id: null, matched_name: null, confident: false, proposed_category: "carne" }), 1),
      ],
    };

    expect(recipeBody(values).ingredients).toEqual([
      { name: "speck", category: "carne", role: "primary", quantity_text: null },
    ]);
  });
});

describe("prima di mandare", () => {
  it("dice cosa manca o cosa è fuori scala", () => {
    expect(validationProblem(EMPTY_FORM)).toMatch(/servono un titolo e un procedimento/i);
    expect(validationProblem({ ...EMPTY_FORM, title: "x", instructions: "y", servingsText: "0" })).toMatch(/tra 1 e 50/);
    expect(validationProblem({ ...EMPTY_FORM, title: "x", instructions: "y" })).toBeNull();
  });
});

describe("il nome si scrive una volta", () => {
  it("la nota di una riga da creare non ripete il nome", () => {
    const speck = lineFromDraft(
      bozza({ raw_name: "Speck", ingredient_id: null, matched_name: null, confident: false, proposed_category: "carne" }),
      0
    );
    expect(matchNote(speck)).toBe("da creare salvando");
    // «non in anagrafica» tiene il nome: un test di «Scrivi una ricetta» lo cerca lì
    expect(matchNote(lineFromDraft(bozza({ raw_name: "Zafferano", ingredient_id: null, matched_name: null }), 1)))
      .toBe("Zafferano non in anagrafica, sarà escluso");
  });

  it("la nota dell'aggancio compare solo se dice qualcosa di diverso", () => {
    expect(showsMatch(lineFromIngredient(ZAFFERANO))).toBe(false);
    expect(showsMatch(valuesFromRecipe(DETAIL).lines[0])).toBe(false);
    expect(showsMatch(lineFromDraft(bozza({}), 0))).toBe(false);
    expect(showsMatch(lineFromDraft(bozza({ raw_name: "basilico fresco", matched_name: "basilico" }), 0))).toBe(true);
    expect(showsMatch(lineFromDraft(bozza({ confident: false }), 0))).toBe(true);
    expect(showsMatch(lineFromDraft(bozza({ ingredient_id: null, matched_name: null }), 0))).toBe(true);
  });
});
