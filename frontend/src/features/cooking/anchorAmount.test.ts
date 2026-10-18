import { describe, expect, it } from "vitest";
import { AMOUNT_EMPTY, AMOUNT_NOT_A_NUMBER, AMOUNT_ZERO, readAmount } from "./anchorAmount";

describe("readAmount", () => {
  // la forma e basta: se la dose vada bene per la ricetta lo dice il server
  it.each([
    ["150", "150"],
    ["150,5", "150.5"],
    ["1.5", "1.5"],
    [" 80 ", "80"],
    ["0,001", "0.001"],
    ["9999999", "9999999"],
  ])("«%s» parte come %s", (scritto, atteso) => {
    expect(readAmount(scritto)).toEqual({ amount: atteso });
  });

  it.each([
    ["", AMOUNT_EMPTY],
    ["   ", AMOUNT_EMPTY],
    ["tanta", AMOUNT_NOT_A_NUMBER],
    ["-5", AMOUNT_NOT_A_NUMBER],
    // tre decimali, come la colonna delle dosi
    ["1,2345", AMOUNT_NOT_A_NUMBER],
    // l'unità sta accanto alla casella, non dentro
    ["1,5 g", AMOUNT_NOT_A_NUMBER],
    // sette cifre intere: sotto i 10 000 000 che il server accetta
    ["10000000", AMOUNT_NOT_A_NUMBER],
    ["1e3", AMOUNT_NOT_A_NUMBER],
    ["0", AMOUNT_ZERO],
    ["0,000", AMOUNT_ZERO],
  ])("«%s» non parte: %s", (scritto, perche) => {
    expect(readAmount(scritto)).toEqual({ problem: perche });
  });
});
