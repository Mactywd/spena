import { describe, expect, it } from "vitest";
import {
  callsText,
  formatDay,
  formatDayShort,
  formatRange,
  formatShare,
  formatUsd,
  peakDay,
  unpricedText,
} from "./format";

// `Intl` mette uno spazio non separabile fra la cifra e «$»: qui lo si confronta come
// spazio, e un test a parte dice che c'è
const leggibile = (testo: string) => testo.replace(/\u00a0/g, " ");

describe("formatUsd", () => {
  it.each([
    [0, "0,00 $"],
    [0.00005, "< 0,0001 $"],
    [0.0001, "0,0001 $"],
    [0.000123, "0,0001 $"],
    [0.0123, "0,0123 $"],
    [0.025, "0,025 $"],
    [0.5, "0,50 $"],
    [0.123456, "0,1235 $"],
    [1.5, "1,50 $"],
    [12.345678, "12,35 $"],
  ])("%s dollari si scrivono «%s»", (valore, atteso) => {
    expect(leggibile(formatUsd(valore))).toBe(atteso);
  });

  it("la cifra e il simbolo non si separano andando a capo", () => {
    expect(formatUsd(0.5)).toBe("0,50 $");
  });
});

describe("formatShare", () => {
  it.each([
    [0, "0%"],
    [0.004, "< 1%"],
    [0.16, "16%"],
    [0.8333, "83%"],
    [1, "100%"],
  ])("la quota %s si scrive «%s»", (quota, atteso) => {
    expect(formatShare(quota)).toBe(atteso);
  });
});

describe("formatRange", () => {
  it.each([
    ["2026-10-13", "2026-10-13", "13 ottobre"],
    ["2026-10-01", "2026-10-13", "dall'1 al 13 ottobre"],
    ["2026-10-02", "2026-10-08", "dal 2 all'8 ottobre"],
    ["2026-09-14", "2026-10-13", "dal 14 settembre al 13 ottobre"],
    ["2026-09-17", "2026-10-11", "dal 17 settembre all'11 ottobre"],
    ["2025-12-20", "2026-01-18", "dal 20 dicembre 2025 al 18 gennaio 2026"],
  ])("da %s a %s si legge «%s»", (primo, ultimo, atteso) => {
    expect(formatRange(primo, ultimo)).toBe(atteso);
  });
});

describe("formatDay e formatDayShort", () => {
  it.each([
    ["2026-10-05", "5 ottobre", "5 ott"],
    ["2026-09-17", "17 settembre", "17 set"],
  ])("%s è «%s», e in breve «%s»", (iso, lungo, breve) => {
    expect(formatDay(iso)).toBe(lungo);
    expect(formatDayShort(iso)).toBe(breve);
  });
});

describe("callsText", () => {
  it.each([
    [1, "1 chiamata"],
    [42, "42 chiamate"],
  ])("%s → «%s»", (chiamate, atteso) => {
    expect(callsText(chiamate)).toBe(atteso);
  });
});

describe("unpricedText", () => {
  it.each([
    [1, "1 senza un costo dichiarato (di solito, una chiamata fallita): non è nel totale."],
    [3, "3 senza un costo dichiarato (di solito, chiamate fallite): non sono nel totale."],
  ])("%s → «%s»", (senza, atteso) => {
    expect(unpricedText(senza)).toBe(atteso);
  });
});

describe("peakDay", () => {
  it("il giorno più caro, il primo a parità", () => {
    const giorni = [
      { day: "2026-10-01", cost_usd: 0.002 },
      { day: "2026-10-02", cost_usd: 0.021 },
      { day: "2026-10-03", cost_usd: 0.021 },
    ];
    expect(peakDay(giorni)).toEqual({ day: "2026-10-02", cost_usd: 0.021 });
  });

  it("nessuno, se nessun giorno ha una spesa", () => {
    expect(peakDay([{ day: "2026-10-01", cost_usd: 0 }])).toBeNull();
  });
});
