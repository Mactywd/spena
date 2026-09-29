import { afterEach, describe, expect, it, vi } from "vitest";
import { lowerBoundFrom, nextPageOffset, searchRecipes, totalFrom, type RecipePage } from "./api";
import type { RecipeSummary } from "../../domain/types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("totalFrom", () => {
  // meglio nessun conteggio che uno inventato: quel che non è un intero non è un totale
  const casi: [string | null, number | null][] = [
    ["42", 42],
    ["0", 0],
    [null, null],
    ["-1", null],
    ["3.5", null],
    ["tante", null],
  ];
  it.each(casi)("«%s» → %s", (valore, atteso) => {
    const headers = new Headers(valore === null ? {} : { "X-Total-Count": valore });
    expect(totalFrom(headers)).toBe(atteso);
  });
});

describe("lowerBoundFrom", () => {
  // vero solo quando l'intestazione vale esattamente "1": la piscina dei candidati
  // era piena, e il totale conta solo quelli guardati, non l'intero ricettario (R-B)
  const casi: [string | null, boolean][] = [
    ["1", true],
    [null, false],
    ["0", false],
    ["true", false],
  ];
  it.each(casi)("«%s» → %s", (valore, atteso) => {
    const headers = new Headers(
      valore === null ? {} : { "X-Total-Count-Lower-Bound": valore }
    );
    expect(lowerBoundFrom(headers)).toBe(atteso);
  });
});

describe("nextPageOffset", () => {
  function pagina(quante: number, total: number | null): RecipePage {
    return {
      recipes: Array.from({ length: quante }, (_, n) => ({ id: `r${n}` }) as RecipeSummary),
      total,
      totalIsLowerBound: false,
    };
  }

  const casi: [string, RecipePage[], number | undefined][] = [
    ["col totale, ne mancano ancora", [pagina(30, 45)], 30],
    ["col totale, una pagina piena che è anche l'ultima chiude", [pagina(30, 30)], undefined],
    ["col totale, la seconda pagina chiude il conto", [pagina(30, 34), pagina(4, 34)], undefined],
    ["senza totale, una pagina piena ne promette un'altra", [pagina(30, null)], 30],
    ["senza totale, una pagina corta è l'ultima", [pagina(12, null)], undefined],
    ["una pagina vuota chiude, qualunque cosa dica il totale", [pagina(30, 40), pagina(0, 40)], undefined],
  ];
  it.each(casi)("%s", (_caso, pagine, atteso) => {
    expect(nextPageOffset(pagine[pagine.length - 1], pagine)).toBe(atteso);
  });
});

describe("searchRecipes", () => {
  it("porta le ricette e il totale dell'intestazione", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([{ id: "r1" }]), {
        status: 200,
        headers: { "X-Total-Count": "12" },
      })
    );
    vi.stubGlobal("fetch", spy);

    await expect(searchRecipes({ query: "pasta", offset: 30 })).resolves.toEqual({
      recipes: [{ id: "r1" }],
      total: 12,
      totalIsLowerBound: false,
    });
    expect(String(spy.mock.calls[0][0])).toBe(
      "/api/v1/recipes/search?q=pasta&limit=30&offset=30"
    );
  });

  it("con la piscina piena il totale è solo un minimo (R-B)", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([{ id: "r1" }]), {
        status: 200,
        headers: { "X-Total-Count": "12", "X-Total-Count-Lower-Bound": "1" },
      })
    );
    vi.stubGlobal("fetch", spy);

    await expect(searchRecipes({ query: "pasta" })).resolves.toEqual({
      recipes: [{ id: "r1" }],
      total: 12,
      totalIsLowerBound: true,
    });
  });
});
