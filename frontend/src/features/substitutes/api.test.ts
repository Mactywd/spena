import { afterEach, describe, expect, it, vi } from "vitest";
import {
  loadLineSubstitution,
  resetLineSubstitution,
  saveIngredientSubstitution,
  saveLineSubstitution,
} from "./api";
import type { LineSubstitution } from "./types";

const VUOTA: LineSubstitution = {
  ingredient_id: "i-pasta", ingredient_name: "pasta", context: "salato", scope: null,
  verdict: null, decided_by: null, substitutes: [], ai_failed: false,
};
const OMETTERE: LineSubstitution = { ...VUOTA, scope: "general", verdict: "omit", decided_by: "ai" };

function stubFetch(risposte: Record<string, unknown>) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const chiave = `${init?.method ?? "GET"} ${String(url)}`;
    const corpo = risposte[chiave];
    return Promise.resolve(
      corpo === undefined ? new Response(null, { status: 204 }) : new Response(JSON.stringify(corpo), { status: 200 })
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("le chiamate dei sostituti", () => {
  it("una risposta salvata si legge e basta", async () => {
    const spy = stubFetch({ "GET /api/v1/recipes/r1/substitutes/i-pasta": OMETTERE });
    expect(await loadLineSubstitution("r1", "i-pasta")).toEqual(OMETTERE);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("senza una risposta la chiede al server, che la chiede all'AI", async () => {
    const spy = stubFetch({
      "GET /api/v1/recipes/r1/substitutes/i-pasta": VUOTA,
      "POST /api/v1/recipes/r1/substitutes/i-pasta/ask": OMETTERE,
    });
    expect(await loadLineSubstitution("r1", "i-pasta")).toEqual(OMETTERE);
    expect(spy.mock.calls.map(([url, init]) => `${init?.method ?? "GET"} ${String(url)}`)).toEqual([
      "GET /api/v1/recipes/r1/substitutes/i-pasta",
      "POST /api/v1/recipes/r1/substitutes/i-pasta/ask",
    ]);
  });

  it("la correzione della ricetta va con PUT, il ritorno con DELETE", async () => {
    const spy = stubFetch({ "PUT /api/v1/recipes/r1/substitutes/i-pasta": OMETTERE });
    await saveLineSubstitution("r1", "i-pasta", { verdict: "omit", substitutes: [] });
    await resetLineSubstitution("r1", "i-pasta");
    const [put, del] = spy.mock.calls;
    expect(put[1]?.method).toBe("PUT");
    expect(JSON.parse(String(put[1]?.body))).toEqual({ verdict: "omit", substitutes: [] });
    expect(`${del[1]?.method} ${String(del[0])}`).toBe("DELETE /api/v1/recipes/r1/substitutes/i-pasta");
  });

  it("la voce generale si scrive per contesto", async () => {
    const spy = stubFetch({ "PUT /api/v1/ingredients/i-pasta/substitutes/dolce": { ingredient_id: "i-pasta", contexts: [], recipe_overrides: 0 } });
    await saveIngredientSubstitution("i-pasta", "dolce", { verdict: "irreplaceable", substitutes: [] });
    expect(String(spy.mock.calls[0][0])).toBe("/api/v1/ingredients/i-pasta/substitutes/dolce");
  });
});
