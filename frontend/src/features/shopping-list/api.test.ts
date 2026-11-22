import { describe, expect, it } from "vitest";
import { ingredientSearchKey } from "./api";

describe("ingredientSearchKey", () => {
  it("con il limite la chiave è un'altra: Abbina e l'Anagrafica non si leggono a vicenda", () => {
    expect(ingredientSearchKey("pomodoro", undefined, false, 50)).not.toEqual(
      ingredientSearchKey("pomodoro", undefined, false)
    );
  });

  it("senza limite le chiavi sono quelle di sempre", () => {
    expect(ingredientSearchKey("pomodoro")).toEqual(["ingredients", "pomodoro", "tutti"]);
    expect(ingredientSearchKey("pomodoro", "food")).toEqual(["ingredients", "pomodoro", "food"]);
    expect(ingredientSearchKey("pomodoro", undefined, false)).toEqual([
      "ingredients", "pomodoro", "tutti", "intero",
    ]);
  });
});
