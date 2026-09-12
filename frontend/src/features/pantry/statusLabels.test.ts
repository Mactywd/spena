import { describe, expect, it } from "vitest";
import { STATUS_LABELS, STATUS_TONE } from "./statusLabels";
import type { PantryStatus } from "../../domain/types";

const STATUSES: PantryStatus[] = ["available", "low", "finished"];

describe("il modo in cui il sistema presenta uno stato", () => {
  // Le parole e i colori descrivono lo stesso insieme di stati. Se qualcuno aggiunge
  // uno stato e dimentica una delle due mappe, lo schermo lo mostra senza colore (o
  // senza nome) e il difetto si vede solo a occhio, su uno stato raro.
  it("dà a ogni stato sia una parola sia un colore", () => {
    expect(Object.keys(STATUS_TONE).sort()).toEqual(Object.keys(STATUS_LABELS).sort());
    expect(Object.keys(STATUS_TONE).sort()).toEqual([...STATUSES].sort());
  });

  it.each(STATUSES)("%s ha un riempimento e una tinta", (status) => {
    expect(STATUS_TONE[status].fill).toMatch(/\S/);
    expect(STATUS_TONE[status].tint).toMatch(/\S/);
  });

  // Il cuore della faccenda: `low` è l'unico stato che cambia la risposta alla
  // domanda «si può cucinare?», perché un secondario lo accetta e un primario no.
  // Colorarlo come `available` rende invisibile la sola regola che ripaga chi tiene
  // aggiornata la dispensa, ed è esattamente com'era prima di questo test.
  it("non colora «quasi finito» come «disponibile»", () => {
    expect(STATUS_TONE.low.fill).not.toBe(STATUS_TONE.available.fill);
    expect(STATUS_TONE.low.tint).not.toBe(STATUS_TONE.available.tint);
  });

  it("distingue tutti e tre gli stati tra loro", () => {
    const fills = STATUSES.map((status) => STATUS_TONE[status].fill);
    expect(new Set(fills).size).toBe(STATUSES.length);
  });
});
