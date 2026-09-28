import { describe, expect, it } from "vitest";
import { expiryText } from "./expiryLabels";

describe("expiryText", () => {
  // «oggi» è il 28 settembre 2026, a mezzogiorno ora locale
  const today = new Date(2026, 8, 28, 12, 0);

  it.each([
    // il verdetto «soon» viene dal backend: qui si sceglie solo come dirlo
    ["2026-09-28", "soon", "scade oggi"],
    ["2026-09-29", "soon", "scade domani"],
    ["2026-10-01", "soon", "scade tra 3 gg"],
    // il fuso del telefono può non essere quello di Roma: un «soon» già passato si
    // dice «oggi», non «tra -1 gg»
    ["2026-09-27", "soon", "scade oggi"],
    ["2026-09-27", "expired", "scadeva ieri"],
    ["2026-09-20", "expired", "scadeva il 20 set"],
    // «expired» con la data di oggi è un disaccordo di fuso: si dice ieri
    ["2026-09-28", "expired", "scadeva ieri"],
    ["2026-11-15", null, "scade il 15 nov"],
    ["2027-01-10", null, "scade il 10 gen 2027"],
    ["2025-12-31", "expired", "scadeva il 31 dic 2025"],
  ] as const)("%s (%s) → %s", (expiresOn, expiry, expected) => {
    expect(expiryText(expiresOn, expiry, today)).toBe(expected);
  });

  it("non sbaglia giorno al cambio dell'ora legale", () => {
    // il 25 ottobre 2026 l'Italia torna all'ora solare: quel giorno dura 25 ore
    const sabato = new Date(2026, 9, 24, 23, 30);
    expect(expiryText("2026-10-26", "soon", sabato)).toBe("scade tra 2 gg");
  });
});
