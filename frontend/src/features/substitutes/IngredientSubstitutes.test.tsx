import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { IngredientSubstitutes } from "./IngredientSubstitutes";
import type { IngredientSubstitutions } from "./types";

const BASE = "/api/v1/ingredients/i-burro/substitutes";
const SCHEDA: IngredientSubstitutions = {
  ingredient_id: "i-burro",
  recipe_overrides: 2,
  contexts: [
    { context: "salato", recipes: 1, verdict: "substitutes", decided_by: "ai",
      substitutes: [{ ingredient_id: "i-margarina", name: "margarina", note: "metà dose" }] },
    { context: "dolce", recipes: 12, verdict: null, decided_by: null, substitutes: [] },
  ],
};

type FetchRoute = (path: string, method: string, init?: RequestInit) => [unknown, number];

function stubRoutedFetch(route: FetchRoute) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init?.method ?? "GET", init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <IngredientSubstitutes ingredientId="i-burro" ingredientName="burro" />
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("IngredientSubstitutes", () => {
  it("una scheda per contesto, la voce dell'AI da rivedere, le correzioni delle ricette", async () => {
    stubRoutedFetch(() => [SCHEDA, 200]);
    renderSection();
    expect(await screen.findByRole("heading", { name: "Nei piatti salati · in 1 ricetta" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sostituti" })).toBeInTheDocument();
    expect(screen.getByText("Margarina")).toBeInTheDocument();
    expect(screen.getByText("Deciso dall'AI: da rivedere.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Va bene così: nei piatti salati" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Correggi: nei piatti salati" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Nei dolci · in 12 ricette" })).toBeInTheDocument();
    expect(
      screen.getByText("Nessun suggerimento ancora: lo chiedo all'AI la prima volta che lo sostituisci in una ricetta.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Scrivi tu: nei dolci" })).toBeInTheDocument();
    expect(screen.getByText("Corretto a mano in 2 ricette.")).toBeInTheDocument();
  });

  it("«Va bene così» rimanda la risposta com'è, e diventa scelta a mano", async () => {
    const confermata: IngredientSubstitutions = {
      ...SCHEDA, contexts: [{ ...SCHEDA.contexts[0], decided_by: "human" }, SCHEDA.contexts[1]],
    };
    const spy = stubRoutedFetch((_path, method) => [method === "PUT" ? confermata : SCHEDA, 200]);
    renderSection();
    await userEvent.click(await screen.findByRole("button", { name: "Va bene così: nei piatti salati" }));

    expect(await screen.findByText("Scelto a mano.")).toBeInTheDocument();
    expect(screen.queryByText("Deciso dall'AI: da rivedere.")).toBeNull();
    const put = spy.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "PUT")!;
    expect(String(put[0])).toBe(`${BASE}/salato`);
    expect(JSON.parse(String((put[1] as RequestInit).body))).toEqual({
      verdict: "substitutes", substitutes: [{ ingredient_id: "i-margarina", note: "metà dose" }],
    });
  });

  it("«Scrivi tu» scrive la voce dolce", async () => {
    const scritta: IngredientSubstitutions = {
      ...SCHEDA,
      contexts: [SCHEDA.contexts[0], { context: "dolce", recipes: 12, verdict: "irreplaceable", decided_by: "human", substitutes: [] }],
    };
    const spy = stubRoutedFetch((_path, method) => [method === "PUT" ? scritta : SCHEDA, 200]);
    renderSection();
    await userEvent.click(await screen.findByRole("button", { name: "Scrivi tu: nei dolci" }));
    expect(screen.getByRole("group", { name: "Al posto di burro, nei dolci:" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Insostituibile" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));

    expect(await screen.findByText("Insostituibile: senza burro il piatto non si fa.")).toBeInTheDocument();
    const put = spy.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "PUT")!;
    expect(String(put[0])).toBe(`${BASE}/dolce`);
  });

  it("«Annulla» chiude il modulo e ridà il fuoco a «Correggi»", async () => {
    stubRoutedFetch(() => [SCHEDA, 200]);
    renderSection();
    await userEvent.click(await screen.findByRole("button", { name: "Correggi: nei piatti salati" }));
    expect(screen.getByRole("textbox", { name: "Nota per margarina" })).toHaveValue("metà dose");
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("button", { name: "Correggi: nei piatti salati" })).toHaveFocus();
  });

  it("un ingrediente in nessuna ricetta lo dice", async () => {
    stubRoutedFetch(() => [{ ingredient_id: "i-burro", contexts: [], recipe_overrides: 0 }, 200]);
    renderSection();
    expect(
      await screen.findByText("Non è in nessuna ricetta: i sostituti servono dentro una ricetta.")
    ).toBeInTheDocument();
  });

  it("un guasto lascia «Riprova»", async () => {
    stubRoutedFetch(() => [{ detail: "x" }, 500]);
    renderSection();
    expect(await screen.findByText("Non sono riuscito a leggere i sostituti.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Riprova a leggere i sostituti" })).toBeInTheDocument();
  });
});
