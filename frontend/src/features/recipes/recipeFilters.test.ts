import { afterEach, describe, expect, it } from "vitest";
import {
  EMPTY_FILTERS,
  FILTERS_KEY,
  activeFilterCount,
  filtersButtonName,
  loadFilters,
  resultsLabel,
  saveFilters,
  type RecipeFilters,
} from "./recipeFilters";
import type { Ingredient } from "../../domain/types";

const POMODORO: Ingredient = {
  id: "i9", name: "pomodoro", display_name: "Pomodoro", category: "verdura", kind: "food",
};
const BASILICO: Ingredient = {
  id: "i7", name: "basilico", display_name: "Basilico", category: "verdura", kind: "food",
};

/** Una memoria di prova: la stessa interfaccia della `sessionStorage`, in una mappa. */
class MemoriaFinta {
  private valori = new Map<string, string>();
  get length() {
    return this.valori.size;
  }
  clear() {
    this.valori.clear();
  }
  getItem(key: string) {
    return this.valori.get(key) ?? null;
  }
  key(index: number) {
    return [...this.valori.keys()][index] ?? null;
  }
  removeItem(key: string) {
    this.valori.delete(key);
  }
  setItem(key: string, value: string) {
    this.valori.set(key, value);
  }
}

function memoria(): Storage {
  return new MemoriaFinta() as unknown as Storage;
}

const PIENI: RecipeFilters = {
  query: "pasta",
  // zero, non l'assenza di soglia: «Ora» deve tornare «Ora»
  maxMissing: 0,
  category: "Primi piatti",
  ingredients: [POMODORO, BASILICO],
};

afterEach(() => {
  sessionStorage.clear();
});

describe("activeFilterCount", () => {
  // la categoria conta uno, ogni ingrediente uno; parole e scala stanno fuori dal
  // pannello, sempre a video, e non contano
  const casi: [string, RecipeFilters, number][] = [
    ["niente", EMPTY_FILTERS, 0],
    ["la categoria", { ...EMPTY_FILTERS, category: "Primi piatti" }, 1],
    ["due ingredienti", { ...EMPTY_FILTERS, ingredients: [POMODORO, BASILICO] }, 2],
    [
      "categoria e due ingredienti",
      { ...EMPTY_FILTERS, category: "Dolci", ingredients: [POMODORO, BASILICO] },
      3,
    ],
    ["parole e scala non contano", { ...EMPTY_FILTERS, query: "pasta", maxMissing: 2 }, 0],
  ];
  it.each(casi)("%s", (_caso, filtri, atteso) => {
    expect(activeFilterCount(filtri)).toBe(atteso);
  });
});

describe("filtersButtonName", () => {
  const casi: [number, string][] = [
    [0, "Filtri"],
    [1, "Filtri, 1 attivo"],
    [3, "Filtri, 3 attivi"],
  ];
  it.each(casi)("%s → «%s»", (numero, atteso) => {
    // il nome comincia con la scritta a video (label-in-name)
    expect(filtersButtonName(numero)).toBe(atteso);
  });
});

describe("resultsLabel", () => {
  const casi: [number | null, boolean, string | null][] = [
    [null, false, null],
    [0, false, "Nessuna ricetta"],
    [1, false, "1 ricetta"],
    [42, false, "42 ricette"],
    [42, true, "almeno 42 ricette"],
    [1, true, "almeno 1 ricetta"],
    [0, true, "Nessuna ricetta"],
    [null, true, null],
  ];
  it.each(casi)("%s, lowerBound=%s → %s", (totale, lowerBound, atteso) => {
    expect(resultsLabel(totale, lowerBound)).toBe(atteso);
  });
});

describe("la memoria dei filtri", () => {
  it("salvati e riletti, i filtri tornano uguali", () => {
    const store = memoria();
    saveFilters(PIENI, store);
    expect(loadFilters(store)).toEqual(PIENI);
  });

  it("senza memoria, o con la memoria vuota, si parte vuoti", () => {
    expect(loadFilters(null)).toEqual(EMPTY_FILTERS);
    expect(loadFilters(memoria())).toEqual(EMPTY_FILTERS);
  });

  it("un contenuto che non è JSON, o non è un oggetto, non rompe niente", () => {
    const store = memoria();
    store.setItem(FILTERS_KEY, "{non è json");
    expect(loadFilters(store)).toEqual(EMPTY_FILTERS);
    store.setItem(FILTERS_KEY, "42");
    expect(loadFilters(store)).toEqual(EMPTY_FILTERS);
  });

  it("quel che non si riconosce si scarta pezzo per pezzo, e il resto resta", () => {
    const store = memoria();
    store.setItem(FILTERS_KEY, JSON.stringify({
      query: 42,
      // non è un gradino della scala
      maxMissing: 7,
      category: "Primi piatti",
      ingredients: [POMODORO, { id: "x" }, POMODORO, "basilico"],
    }));
    expect(loadFilters(store)).toEqual({
      query: "",
      maxMissing: null,
      category: "Primi piatti",
      ingredients: [POMODORO],
    });
  });

  it("una memoria che lancia, in lettura o in scrittura, non rompe niente", () => {
    // dati del sito bloccati, finestra privata, memoria piena
    const rotta = {
      getItem: () => {
        throw new Error("bloccata");
      },
      setItem: () => {
        throw new Error("piena");
      },
    } as unknown as Storage;
    expect(loadFilters(rotta)).toEqual(EMPTY_FILTERS);
    expect(() => saveFilters(PIENI, rotta)).not.toThrow();
  });

  it("di norma usa la sessionStorage del browser: vale finché l'app è aperta", () => {
    saveFilters(PIENI);
    expect(JSON.parse(sessionStorage.getItem(FILTERS_KEY)!)).toEqual(PIENI);
    expect(loadFilters()).toEqual(PIENI);
  });
});
