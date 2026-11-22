import { afterEach, describe, expect, it } from "vitest";
import { loadWorld, saveWorld, WORLD_KEY } from "./pantryWorld";
import type { PantryWorld } from "./pantryView";

/** Una memoria di prova: la stessa interfaccia della `sessionStorage`, in una mappa
 * (come in `recipeFilters.test.ts`). */
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

afterEach(() => {
  sessionStorage.clear();
});

describe("loadWorld e saveWorld", () => {
  it("senza niente di salvato è «Tutto»", () => {
    expect(loadWorld(memoria())).toBe("all");
  });

  it.each(["all", "food", "non_food"] as PantryWorld[])("rilegge «%s» come l'ha scritto", (world) => {
    const store = memoria();
    saveWorld(world, store);
    expect(store.getItem(WORLD_KEY)).toBe(world);
    expect(loadWorld(store)).toBe(world);
  });

  it.each(["", "cibo", "FOOD", '"food"'])(
    "un valore che non conosce («%s») è «Tutto»: una memoria di un'altra versione non svuota la dispensa",
    (scritto) => {
      const store = memoria();
      store.setItem(WORLD_KEY, scritto);
      expect(loadWorld(store)).toBe("all");
    }
  );

  it("senza memoria (dati del sito bloccati) è «Tutto», e scrivere non fa niente", () => {
    expect(loadWorld(null)).toBe("all");
    expect(() => saveWorld("food", null)).not.toThrow();
  });

  it("una memoria che lancia, in lettura e in scrittura, non rompe niente", () => {
    const rotta = {
      getItem: () => {
        throw new Error("bloccata");
      },
      setItem: () => {
        throw new Error("piena");
      },
    } as unknown as Storage;
    expect(loadWorld(rotta)).toBe("all");
    expect(() => saveWorld("non_food", rotta)).not.toThrow();
  });

  it("di norma usa la sessionStorage del browser: vale finché l'app è aperta", () => {
    saveWorld("non_food");
    expect(sessionStorage.getItem(WORLD_KEY)).toBe("non_food");
    expect(sessionStorage.getItem("spena.dispensa.mondo")).toBe("non_food");
    expect(loadWorld()).toBe("non_food");
  });
});
