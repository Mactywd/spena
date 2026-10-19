import { describe, expect, it } from "vitest";
import type { RequeueResult, SkipCause } from "../../domain/types";
import {
  cookingWaitingText,
  requeueResultMessage,
  skipReasonText,
  skippedTitle,
} from "./skippedWords";

const STRADA_NON_ALIMENTARE =
  "Rendilo un alimento in Anagrafica, o annulla la decisione che lo ha scelto; poi rimettila in coda.";

describe("skipReasonText", () => {
  const casi: [SkipCause, string | null, string][] = [
    [
      "non_food",
      "Panna",
      `Fra gli ingredienti c'è «Panna», che non è un alimento. ${STRADA_NON_ALIMENTARE}`,
    ],
    ["non_food", null, `Uno degli ingredienti non è un alimento. ${STRADA_NON_ALIMENTARE}`],
    [
      "all_ignored",
      null,
      "Tutti i suoi ingredienti sono ignorati, e una ricetta senza ingredienti non entra nel ricettario. Annulla la decisione su uno di loro; poi rimettila in coda.",
    ],
    [
      "unreadable",
      null,
      "Sul sito la pagina non aveva una ricetta leggibile: rimetterla in coda non cambierebbe niente.",
    ],
    ["other", null, "Non è entrata nel ricettario durante l'import."],
  ];
  it.each(casi)("%s (%s)", (causa, nome, frase) => {
    expect(skipReasonText(causa, nome)).toBe(frase);
  });
});

describe("cookingWaitingText", () => {
  it.each([
    [1, "1 cottura registrata aspetta questa ricetta."],
    [3, "3 cotture registrate aspettano questa ricetta."],
  ])("%i", (quante, frase) => {
    expect(cookingWaitingText(quante)).toBe(frase);
  });
});

it("il titolo della sezione porta il numero", () => {
  expect(skippedTitle(7)).toBe("Scartate (7)");
});

describe("requeueResultMessage", () => {
  const BASE: RequeueResult = {
    outcome: "imported",
    title: "Torta alla panna",
    url: "https://esempio.invalid/torta.html",
    recipe_id: "r-torta",
    cooking_relinked: 0,
    cause: null,
    non_food_name: null,
    waiting_terms: [],
  };

  it.each([
    [0, "«Torta alla panna» è entrata nel ricettario."],
    [1, "«Torta alla panna» è entrata nel ricettario. Ha ritrovato 1 cottura."],
    [2, "«Torta alla panna» è entrata nel ricettario. Ha ritrovato 2 cotture."],
  ])("entrata, con %i cotture ritrovate", (cotture, frase) => {
    expect(requeueResultMessage({ ...BASE, cooking_relinked: cotture })).toBe(frase);
  });

  it.each([
    [["Acqua"], "«Torta alla panna» è tornata in coda: aspetta la decisione su «Acqua»."],
    [["Acqua", "Sale"], "«Torta alla panna» è tornata in coda: aspetta le decisioni su «Acqua» e «Sale»."],
    [
      ["Acqua", "Sale", "Pepe"],
      "«Torta alla panna» è tornata in coda: aspetta le decisioni su «Acqua», «Sale» e «Pepe».",
    ],
    [
      ["Acqua", "Sale", "Pepe", "Olio"],
      "«Torta alla panna» è tornata in coda: aspetta le decisioni su «Acqua», «Sale», «Pepe» e un altro.",
    ],
    [
      ["Acqua", "Sale", "Pepe", "Olio", "Aglio"],
      "«Torta alla panna» è tornata in coda: aspetta le decisioni su «Acqua», «Sale», «Pepe» e altri 2.",
    ],
  ])("in coda, in attesa di %j", (termini, frase) => {
    expect(
      requeueResultMessage({ ...BASE, outcome: "waiting", recipe_id: null, waiting_terms: termini })
    ).toBe(frase);
  });

  it("in coda senza nomi da dire", () => {
    expect(requeueResultMessage({ ...BASE, outcome: "waiting", recipe_id: null })).toBe(
      "«Torta alla panna» è tornata in coda: aspetta che i suoi ingredienti siano decisi."
    );
  });

  const ancoraScartata: [SkipCause, string | null, string][] = [
    ["non_food", "Panna", "«Torta alla panna» è ancora scartata: «Panna» non è un alimento."],
    ["non_food", null, "«Torta alla panna» è ancora scartata: un ingrediente non è un alimento."],
    ["all_ignored", null, "«Torta alla panna» è ancora scartata: tutti i suoi ingredienti sono ignorati."],
    ["other", null, "«Torta alla panna» è ancora scartata."],
  ];
  it.each(ancoraScartata)("ancora scartata: %s (%s)", (causa, nome, frase) => {
    expect(
      requeueResultMessage({
        ...BASE,
        outcome: "skipped",
        recipe_id: null,
        cause: causa,
        non_food_name: nome,
      })
    ).toBe(frase);
  });

  it("senza titolo, nomina la pagina col suo indirizzo", () => {
    expect(requeueResultMessage({ ...BASE, title: null })).toBe(
      "«https://esempio.invalid/torta.html» è entrata nel ricettario."
    );
  });
});
