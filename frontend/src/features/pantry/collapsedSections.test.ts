import { describe, expect, it } from "vitest";
import { COLLAPSED_KEY, loadCollapsed, saveCollapsed } from "./collapsedSections";

/** Una memoria di prova: la stessa interfaccia del `localStorage`, in una mappa. */
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

function memoria(valore?: string): Storage {
  const m = new MemoriaFinta();
  if (valore !== undefined) m.setItem(COLLAPSED_KEY, valore);
  return m as unknown as Storage;
}

/** Una memoria che lancia a ogni accesso: i dati del sito bloccati, o lo spazio pieno. */
function memoriaRotta(): Storage {
  return {
    getItem: () => {
      throw new Error("bloccata");
    },
    setItem: () => {
      throw new Error("bloccata");
    },
  } as unknown as Storage;
}

describe("loadCollapsed", () => {
  it("niente salvato: nessun reparto chiuso, la dispensa di oggi", () => {
    expect([...loadCollapsed(memoria())]).toEqual([]);
  });

  it("l'elenco salvato torna", () => {
    expect([...loadCollapsed(memoria('["spezie","casa"]'))].sort()).toEqual(["casa", "spezie"]);
  });

  // illeggibile o non un elenco: tutto aperto, che è la dispensa di oggi
  it.each(["{rotto", '{"spezie":true}', '"spezie"', "null"])("«%s» non è un elenco: tutto aperto", (valore) => {
    expect([...loadCollapsed(memoria(valore))]).toEqual([]);
  });

  it("dentro l'elenco si tiene solo quel che è un nome", () => {
    expect([...loadCollapsed(memoria('["spezie", 3, null, "", {"a": 1}]'))]).toEqual(["spezie"]);
  });

  it("senza memoria (dati del sito bloccati) tutto aperto, e scrivere non lancia", () => {
    expect([...loadCollapsed(null)]).toEqual([]);
    expect(() => saveCollapsed(new Set(["spezie"]), null)).not.toThrow();
  });

  it("una memoria che lancia, leggendo o scrivendo, non ferma niente", () => {
    expect([...loadCollapsed(memoriaRotta())]).toEqual([]);
    expect(() => saveCollapsed(new Set(["spezie"]), memoriaRotta())).not.toThrow();
  });
});

describe("saveCollapsed", () => {
  it("scrive l'elenco in ordine, e si rilegge uguale", () => {
    const m = memoria();
    saveCollapsed(new Set(["spezie", "casa"]), m);
    expect(m.getItem(COLLAPSED_KEY)).toBe('["casa","spezie"]');
    expect([...loadCollapsed(m)].sort()).toEqual(["casa", "spezie"]);
  });
});
