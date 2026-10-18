import { expect, test } from "@playwright/test";
import { giornoDiRoma } from "./giornoDiRoma.ts";

// Il backend giudica le scadenze nel giorno di Europe/Rome (`PANTRY_TZ`): le date delle
// prove si calcolano nello stesso giorno. Con `toISOString()`, in UTC, fra mezzanotte e
// le 2 ora italiana la prova mandava il giorno prima, e falliva («tra 4 gg» invece di
// «tra 5 gg», T3 Consegna 6a). Questa prova non apre pagine: prova solo l'aiuto.
test.describe("giornoDiRoma", () => {
  test("alle 00:30 italiane è già il giorno dopo di UTC", () => {
    const adesso = new Date("2026-10-13T22:30:00Z"); // 00:30 del 14 a Roma (ora legale, +2)
    expect(giornoDiRoma(0, adesso)).toBe("2026-10-14");
    expect(giornoDiRoma(5, adesso)).toBe("2026-10-19");
  });

  test("di pomeriggio è lo stesso giorno", () => {
    expect(giornoDiRoma(3, new Date("2026-10-14T13:00:00Z"))).toBe("2026-10-17");
  });

  test("attraverso il cambio d'ora del 25 ottobre i giorni restano giorni di calendario", () => {
    // 00:30 del 25 a Roma (ancora ora legale): fra un giorno è il 26, anche se quel giorno
    // dura 25 ore
    expect(giornoDiRoma(1, new Date("2026-10-24T22:30:00Z"))).toBe("2026-10-26");
    // 00:30 del 26 a Roma (ora solare, +1)
    expect(giornoDiRoma(0, new Date("2026-10-25T23:30:00Z"))).toBe("2026-10-26");
  });
});
