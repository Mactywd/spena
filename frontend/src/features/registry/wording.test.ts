import { describe, expect, it } from "vitest";
import { usageText } from "./wording";

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
