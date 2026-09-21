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

  it("un anno a una cifra resta quell'anno, non diventa il Novecento", () => {
    // `new Date(2, 9, 15)` non è l'anno 2: il costruttore posizionale mappa 0-99
    // sul 1900-1999. Una data così si scrive da sé battendo a mano nel campo, che
    // è completo a ogni segmento: il primo tasto dell'anno la produce. Mostrarla
    // come «15/10/1902» aggiunge una bugia a un valore già sbagliato — chi rilegge
    // la riga per capire cos'è successo non ritrova quel che ha battuto.
    expect(formatExpiry("0002-10-15", null)).toBe("Scade il 15/10/2");
  });
});
