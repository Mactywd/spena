import { describe, expect, it } from "vitest";
import { mergeDoneText, mergePreviewText, mergeSlowWarning, movedText, pantryText, usageText } from "./wording";
import type { MergeCounts, ProductDetail } from "../../domain/types";

describe("usageText", () => {
  it("dice dove è usato un ingrediente, come l'esempio della spec", () => {
    expect(usageText({ recipes: 42, pantry: 1, shopping: 1 })).toBe(
      "in 42 ricette · 1 in dispensa · in lista"
    );
  });

  it("al singolare, e senza le parti che non ci sono", () => {
    expect(usageText({ recipes: 1, pantry: 0, shopping: 0 })).toBe("in 1 ricetta");
    expect(usageText({ recipes: 0, pantry: 2, shopping: 0 })).toBe("in nessuna ricetta · 2 in dispensa");
  });
});

const CONTI: MergeCounts = {
  dry_run: true, loser_name: "pomodori", winner_id: "i-pomodoro", winner_name: "pomodoro",
  recipes_rebuilt: 2, recipe_lines_moved: 1, pantry_items: 1, shopping_items: 0,
  shopping_items_dropped: 0, products: 0, aliases: 2, cooking_events_relinked: 0,
};

describe("mergePreviewText", () => {
  it("è la frase della spec, parola per parola", () => {
    expect(mergePreviewText(CONTI)).toBe(
      "Si spostano 3 ricette, 1 elemento di dispensa, 2 alias. «pomodori» diventa un alias di «pomodoro». Non si annulla."
    );
  });

  it("al singolare, e con niente da spostare", () => {
    const una = { ...CONTI, recipes_rebuilt: 0, recipe_lines_moved: 1, pantry_items: 0, aliases: 0 };
    expect(mergePreviewText(una)).toBe(
      "Si sposta 1 ricetta. «pomodori» diventa un alias di «pomodoro». Non si annulla."
    );
    const niente = { ...una, recipe_lines_moved: 0 };
    expect(mergePreviewText(niente)).toBe(
      "Non si sposta niente. «pomodori» diventa un alias di «pomodoro». Non si annulla."
    );
  });

  it("dice le cotture che si ri-legano: chi fonde lo vuole sapere (spec §5.2)", () => {
    expect(mergePreviewText({ ...CONTI, cooking_events_relinked: 2 })).toContain(
      "2 cotture già registrate ritrovano la loro ricetta."
    );
  });
});

describe("la voce di lista doppia", () => {
  it("l'anteprima dice che la voce del perdente si toglie, perché il vincitore è già in lista", () => {
    expect(mergePreviewText({ ...CONTI, shopping_items_dropped: 1 })).toBe(
      "Si spostano 3 ricette, 1 elemento di dispensa, 2 alias. «pomodoro» è già in lista: " +
        "la voce di «pomodori» si toglie. «pomodori» diventa un alias di «pomodoro». Non si annulla."
    );
    expect(mergePreviewText({ ...CONTI, shopping_items_dropped: 2 })).toContain(
      "«pomodoro» è già in lista: le 2 voci di «pomodori» si tolgono."
    );
  });

  it("l'esito lo ripete sulla scheda del vincitore", () => {
    expect(mergeDoneText({ ...CONTI, dry_run: false, shopping_items_dropped: 1 })).toBe(
      "Uniti: «pomodori» ora è un alias di «pomodoro». Spostati qui: 3 ricette, 1 elemento di " +
        "dispensa, 2 alias. «pomodoro» era già in lista: la voce di «pomodori» è stata tolta."
    );
  });
});

describe("mergeDoneText", () => {
  it("dice l'esito sulla scheda del vincitore", () => {
    expect(mergeDoneText({ ...CONTI, dry_run: false })).toBe(
      "Uniti: «pomodori» ora è un alias di «pomodoro». Spostati qui: 3 ricette, 1 elemento di dispensa, 2 alias."
    );
  });
});

describe("mergeSlowWarning", () => {
  it("avvisa sopra la soglia delle 1.000 ricette (deciso con Mattia al Task 11)", () => {
    expect(mergeSlowWarning(1001)).toContain("Può volerci qualche minuto");
  });

  it("non avvisa esattamente alla soglia", () => {
    expect(mergeSlowWarning(1000)).toBeNull();
  });
});

describe("movedText", () => {
  const SPOSTATO: ProductDetail = {
    id: "p1", name: "Parmigiano Reggiano 24 mesi", brand: null, barcode: null,
    valid_checksum: null, ingredient: { id: "i1", name: "parmigiano", display_name: "Parmigiano" },
    pantry_items: [{ id: "v1", status: "available", expires_on: null }],
  };

  it("dice sotto cosa è andato, e con quanti elementi di dispensa (spec §6.4)", () => {
    expect(movedText(SPOSTATO)).toBe("Spostato sotto «Parmigiano», con 1 elemento di dispensa.");
    expect(movedText({ ...SPOSTATO, pantry_items: [] })).toBe("Spostato sotto «Parmigiano».");
  });

  it("conta gli elementi in dispensa", () => {
    expect(pantryText(0)).toBe("Nessun elemento in dispensa.");
    expect(pantryText(2)).toBe("2 elementi in dispensa.");
  });
});
