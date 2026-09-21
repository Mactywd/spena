import { describe, expect, it } from "vitest";
import { formatExpiry } from "./expiryLabels";

describe("formatExpiry", () => {
  // `expiresOn` è una data-SENZA-ORA ("2026-09-28"). Lo spec ECMAScript impone che
  // `new Date("2026-09-28")` sia letta come mezzanotte UTC, non mezzanotte locale:
  // in un fuso indietro rispetto a UTC (es. America/New_York, UTC-4/-5) quella
  // mezzanotte UTC cade ancora nel pomeriggio del giorno PRIMA in ora locale, e
  // `toLocaleDateString` la stampa un giorno indietro. Un calendar-day non deve
  // mai attraversare una conversione di fuso orario — è la stessa ragione per cui
  // il backend fissa `PANTRY_TZ`. Questo test non dipende dal fuso della macchina
  // che lo esegue: deve restare verde sia sotto TZ=America/New_York sia sotto
  // TZ=UTC (vedi il report del fix per l'esecuzione in entrambi i fusi).
  it("non arretra di un giorno in un fuso indietro rispetto a UTC", () => {
    expect(formatExpiry("2026-09-28", "soon")).toBe("Scade il 28/09/2026");
  });

  it("non arretra di un giorno nel ramo scaduto", () => {
    expect(formatExpiry("2026-09-20", "expired")).toBe("Scadeva il 20/09/2026");
  });
});
