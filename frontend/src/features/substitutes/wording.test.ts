import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import {
  contextIn,
  contextTitle,
  overridesText,
  provenanceText,
  recipesText,
  saveErrorText,
} from "./wording";

describe("le parole dei sostituti", () => {
  it("dice il contesto dentro una frase e come titolo", () => {
    expect(contextIn("salato")).toBe("nei piatti salati");
    expect(contextIn("dolce")).toBe("nei dolci");
    expect(contextTitle("salato")).toBe("Nei piatti salati");
    expect(contextTitle("dolce")).toBe("Nei dolci");
  });

  it("dice da dove viene una risposta", () => {
    expect(provenanceText({ scope: "general", decided_by: "ai", context: "salato" })).toBe(
      "Suggerito dall'AI per i piatti salati."
    );
    expect(provenanceText({ scope: "general", decided_by: "human", context: "dolce" })).toBe(
      "Scelto a mano per i dolci."
    );
    expect(provenanceText({ scope: "recipe", decided_by: "human", context: "dolce" })).toBe(
      "Scelto a mano per questa ricetta."
    );
  });

  it("conta le ricette e le correzioni", () => {
    expect(recipesText(0)).toBe("in nessuna ricetta");
    expect(recipesText(1)).toBe("in 1 ricetta");
    expect(recipesText(120)).toBe("in 120 ricette");
    expect(overridesText(0)).toBeNull();
    expect(overridesText(1)).toBe("Corretto a mano in 1 ricetta.");
    expect(overridesText(2)).toBe("Corretto a mano in 2 ricette.");
  });

  it("un rifiuto del server si legge com'è, ogni altro guasto no", () => {
    const rifiuto = new ApiError("x", 422, { detail: "«Pasta» non può sostituire sé stesso: scegli un altro ingrediente." });
    expect(saveErrorText(rifiuto)).toBe("«Pasta» non può sostituire sé stesso: scegli un altro ingrediente.");
    // un 422 di validazione ha `detail` come lista: non è una frase da mostrare
    expect(saveErrorText(new ApiError("x", 422, { detail: [{ msg: "x" }] }))).toBe(
      "Non sono riuscito a salvare. Riprova."
    );
    expect(saveErrorText(new ApiError("x", 500, null))).toBe("Non sono riuscito a salvare. Riprova.");
    expect(saveErrorText(new Error("rete"))).toBe("Non sono riuscito a salvare. Riprova.");
  });
});
