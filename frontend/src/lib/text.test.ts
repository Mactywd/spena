import { describe, expect, it } from "vitest";
import { capitalizeFirst, withPrepositionA } from "./text";

describe("capitalizeFirst", () => {
  it.each([
    ["pasta", "Pasta"],
    ["yogurt greco", "Yogurt greco"],
    ["Rigatoni", "Rigatoni"],
    ["", ""],
    ["élite", "Élite"],
  ])("«%s» si legge «%s»", (testo, atteso) => {
    expect(capitalizeFirst(testo)).toBe(atteso);
  });
});

describe("withPrepositionA", () => {
  it.each([
    ["astice", "ad astice"],
    ["Aglio", "ad Aglio"],
    ["àncora", "ad àncora"],
    ["pasta", "a pasta"],
    ["erba cipollina", "a erba cipollina"],
    ["un ingrediente", "a un ingrediente"],
  ])("davanti a «%s» dice «%s»", (parola, atteso) => {
    expect(withPrepositionA(parola)).toBe(atteso);
  });
});
