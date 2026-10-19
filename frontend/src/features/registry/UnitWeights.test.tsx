import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NutritionSection } from "./NutritionSection";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { IngredientNutrition, UnitWeight } from "./nutrition";

const SPICCHIO: UnitWeight = { unit: "u-spicchio", unit_label: "spicchio", grams: 5, state: "decided", decided_by: "ai" };
const TESTA: UnitWeight = { unit: "u-testa", unit_label: "testa", grams: null, state: "undecided", decided_by: null };
const PEZZO: UnitWeight = { unit: "pezzo", unit_label: "pezzo", grams: null, state: "none", decided_by: "human" };

function aglio(weights: UnitWeight[]): IngredientNutrition {
  return {
    state: "undecided", decided_by: null, food: null, nutrients: [], weights,
    source: "CIQUAL 2025", citation: "Anses. 2025. Table de composition nutritionnelle des aliments Ciqual",
  };
}

type Route = (path: string, init?: RequestInit) => [unknown, number] | undefined;

function stub(stato: IngredientNutrition, altro?: Route) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    const [body, status] = altro?.(path, init) ?? (path.endsWith("/ingredients/i-aglio/nutrition") ? [stato, 200] : [{}, 404]);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function chiamate(spy: ReturnType<typeof stub>, metodo: string, pezzo: string) {
  return spy.mock.calls.filter(
    ([url, init]) => String(url).includes(pezzo) && ((init as RequestInit | undefined)?.method ?? "GET") === metodo
  );
}

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: defaultQueryRetryPredicate } } });
  render(
    <QueryClientProvider client={client}>
      <NutritionSection ingredientId="i-aglio" />
    </QueryClientProvider>
  );
}

async function riga(testo: string) {
  return (await screen.findByText(testo)).closest("li")!;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Pesi per unità", () => {
  it("senza coppie dice perché non c'è niente da pesare", async () => {
    stub(aglio([]));
    renderSection();

    expect(await screen.findByRole("heading", { name: "Pesi per unità" })).toBeInTheDocument();
    expect(
      screen.getByText("Nessuna dose da pesare: le sue ricette lo scrivono in grammi o in litri, oppure non lo usano.")
    ).toBeInTheDocument();
  });

  it("una riga per coppia, col peso e chi l'ha deciso", async () => {
    stub(aglio([PEZZO, SPICCHIO, TESTA]));
    renderSection();

    expect(within(await riga("1 spicchio")).getByText("5 g · AI")).toBeInTheDocument();
    expect(within(await riga("1 testa")).getByText("da decidere")).toBeInTheDocument();
    expect(within(await riga("1 pezzo")).getByText("nessun peso · a mano")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Correggi il peso di 1 spicchio" })).toBeInTheDocument();
  });

  it("«Correggi» apre il campo, e «Salva il peso» manda la PUT con la virgola letta", async () => {
    const scritto = aglio([{ ...SPICCHIO, grams: 6.5, decided_by: "human" }]);
    const spy = stub(aglio([SPICCHIO]), (path, init) =>
      init?.method === "PUT" && path.includes("/unit-grams/") ? [scritto, 200] : undefined
    );
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Correggi il peso di 1 spicchio" }));
    const campo = screen.getByLabelText("Grammi in 1 spicchio");
    expect(campo).toHaveValue("5");
    await userEvent.clear(campo);
    await userEvent.type(campo, "6,5");
    await userEvent.click(screen.getByRole("button", { name: "Salva il peso" }));

    expect(await screen.findByText("6,5 g · a mano")).toBeInTheDocument();
    expect(screen.queryByLabelText("Grammi in 1 spicchio")).toBeNull();
    const [url, init] = chiamate(spy, "PUT", "/unit-grams/")[0];
    expect(String(url)).toContain("/ingredients/i-aglio/unit-grams/u-spicchio");
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ grams: 6.5 });
  });

  it("«Salva il peso» non ancora, finché il numero non è più di zero", async () => {
    stub(aglio([TESTA]));
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Correggi il peso di 1 testa" }));
    const campo = screen.getByLabelText("Grammi in 1 testa");
    for (const scritto of ["", "0", "abc"]) {
      await userEvent.clear(campo);
      if (scritto) await userEvent.type(campo, scritto);
      const salva = screen.getByRole("button", { name: "Salva il peso" });
      expect(salva).toHaveAttribute("aria-disabled", "true");
      expect(salva).toHaveAccessibleDescription("Scrivi un numero di grammi più grande di zero.");
    }
    // un peso da decidere non ha niente da annullare
    expect(screen.queryByRole("button", { name: "Annulla il peso" })).toBeNull();
  });

  it("«Annulla il peso» manda la DELETE, e la coppia torna da decidere", async () => {
    const spy = stub(aglio([SPICCHIO]), (_path, init) =>
      init?.method === "DELETE" ? [aglio([{ ...SPICCHIO, grams: null, state: "undecided", decided_by: null }]), 200] : undefined
    );
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Correggi il peso di 1 spicchio" }));
    await userEvent.click(screen.getByRole("button", { name: "Annulla il peso" }));

    expect(within(await riga("1 spicchio")).getByText("da decidere")).toBeInTheDocument();
    expect(chiamate(spy, "DELETE", "/ingredients/i-aglio/unit-grams/u-spicchio")).toHaveLength(1);
  });

  it("un rifiuto si legge col suo perché, e il campo resta aperto", async () => {
    const rifiuto = { code: "bad_grams", detail: "Un peso va da più di 0 a 5000 g: controlla il numero." };
    stub(aglio([SPICCHIO]), (_path, init) => (init?.method === "PUT" ? [rifiuto, 409] : undefined));
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Correggi il peso di 1 spicchio" }));
    await userEvent.clear(screen.getByLabelText("Grammi in 1 spicchio"));
    await userEvent.type(screen.getByLabelText("Grammi in 1 spicchio"), "6000");
    await userEvent.click(screen.getByRole("button", { name: "Salva il peso" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(rifiuto.detail);
    expect(screen.getByLabelText("Grammi in 1 spicchio")).toBeInTheDocument();
  });

  it("un guasto dice di riprovare", async () => {
    stub(aglio([SPICCHIO]), (_path, init) => (init?.method === "PUT" ? [{ detail: "x" }, 500] : undefined));
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Correggi il peso di 1 spicchio" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva il peso" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a salvare il peso. Riprova.");
  });

  it("«Lascia com'è» chiude il campo senza scrivere", async () => {
    const spy = stub(aglio([SPICCHIO]));
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Correggi il peso di 1 spicchio" }));
    await userEvent.click(screen.getByRole("button", { name: "Lascia com'è" }));

    expect(screen.queryByLabelText("Grammi in 1 spicchio")).toBeNull();
    expect(chiamate(spy, "PUT", "/unit-grams/")).toHaveLength(0);
  });

  it("il pezzo si scrive con la parola nell'indirizzo", async () => {
    const spy = stub(aglio([PEZZO]), (_path, init) =>
      init?.method === "PUT" ? [aglio([{ ...PEZZO, grams: 50, state: "decided" }]), 200] : undefined
    );
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Correggi il peso di 1 pezzo" }));
    await userEvent.type(screen.getByLabelText("Grammi in 1 pezzo"), "50");
    await userEvent.click(screen.getByRole("button", { name: "Salva il peso" }));

    expect(await screen.findByText("50 g · a mano")).toBeInTheDocument();
    expect(String(chiamate(spy, "PUT", "/unit-grams/")[0][0])).toContain("/ingredients/i-aglio/unit-grams/pezzo");
  });
});
