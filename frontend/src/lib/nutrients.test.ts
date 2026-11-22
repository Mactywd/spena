import { describe, expect, it } from "vitest";
import { formatNutrient } from "./nutrients";

describe("formatNutrient", () => {
  it.each([
    [18, "kcal", "18 kcal"],
    [357.4, "kcal", "357 kcal"],
    [12.5, "g", "12,5 g"],
    [0.25, "g", "0,25 g"],
    [0.3, "mg", "0,3 mg"],
    [0, "g", "0 g"],
    [2.04, "g", "2 g"],
    [1500, "µg", "1500 µg"],
  ])("%s %s si legge «%s»", (valore, unita, atteso) => {
    expect(formatNutrient(valore, unita)).toBe(atteso);
  });
});
