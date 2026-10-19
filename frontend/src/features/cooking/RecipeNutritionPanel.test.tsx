import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RecipeNutritionPanel } from "./RecipeNutritionPanel";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { RecipeNutrition } from "./recipeNutrition";

const CONTO: RecipeNutrition = {
  basis: "serving",
  servings: 2,
  lines_total: 6,
  lines_counted: 3,
  nutrients: [
    { key: "kcal", label: "Energia", unit: "kcal", main: true, value: 465, lines: 3 },
    { key: "protein", label: "Proteine", unit: "g", main: true, value: 12.4, lines: 2 },
    { key: "fat", label: "Grassi", unit: "g", main: true, value: null, lines: 0 },
  ],
  missing: [
    { ingredient_id: "i-aglio", ingredient_name: "aglio", quantity_text: "1 spicchio", reason: "no_weight", unit_label: "spicchio" },
    { ingredient_id: "i-basilico", ingredient_name: "basilico", quantity_text: "q.b.", reason: "no_quantity", unit_label: null },
    { ingredient_id: "i-uova", ingredient_name: "uova", quantity_text: "2", reason: "no_nutrients", unit_label: null },
  ],
  source: "CIQUAL 2025",
};

function stub(...risposte: [unknown, number][]) {
  const spy = vi.fn((..._args: unknown[]) => {
    const [body, status] = (risposte.length > 1 ? risposte.shift() : undefined) ?? risposte[0];
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: defaultQueryRetryPredicate } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RecipeNutritionPanel recipeId="r-1" />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return client;
}

async function apri() {
  await userEvent.click(screen.getByRole("button", { name: "Mostra i valori nutrizionali" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RecipeNutritionPanel", () => {
  it("è chiuso, e chiuso non chiede niente", () => {
    const spy = stub([CONTO, 200]);
    renderPanel();

    expect(screen.getByRole("heading", { name: "Valori nutrizionali" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mostra i valori nutrizionali" })).toHaveAttribute("aria-expanded", "false");
    expect(spy).not.toHaveBeenCalled();
  });

  it("aperto: la porzione, le righe contate, quelle fuori col perché e la strada", async () => {
    const spy = stub([CONTO, 200]);
    renderPanel();

    await apri();

    expect(await screen.findByRole("table", { name: "A porzione, su 2 porzioni" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "465 kcal" })).toBeInTheDocument();
    expect(screen.getByText("Contate 3 righe su 6.")).toBeInTheDocument();
    expect(screen.getByText("Fuori dal conto:")).toBeInTheDocument();
    const fuori = screen.getAllByRole("listitem");
    expect(fuori.map((riga) => riga.textContent)).toEqual([
      "Aglio (1 spicchio): manca il peso di «spicchio»",
      "Basilico (q.b.): senza una dose da pesare",
      "Uova (2): senza un alimento CIQUAL",
    ]);
    expect(within(fuori[0]).getByRole("link", { name: "Aglio" })).toHaveAttribute("href", "/anagrafica/ingrediente/i-aglio");
    expect(
      screen.getByText("Stima con i valori medi di CIQUAL 2025 e i pesi delle dosi: non è un'etichetta.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nascondi i valori nutrizionali" })).toHaveAttribute("aria-expanded", "true");
    expect(String(spy.mock.calls[0][0])).toContain("/recipes/r-1/nutrition");
  });

  it("un valore che solo alcune righe hanno lo dice", async () => {
    stub([CONTO, 200]);
    renderPanel();

    await apri();

    const proteine = (await screen.findByRole("rowheader", { name: "Proteine" })).closest("tr")!;
    expect(within(proteine).getByText("su 2 righe di 3")).toBeInTheDocument();
    const energia = screen.getByRole("rowheader", { name: "Energia" }).closest("tr")!;
    expect(within(energia).queryByText(/righe di/)).toBeNull();
  });

  it("senza righe contate: niente tabella, e la frase che dice cosa serve", async () => {
    stub([{ ...CONTO, lines_counted: 0, nutrients: [] }, 200]);
    renderPanel();

    await apri();

    expect(
      await screen.findByText(
        "Nessuna riga si può contare ancora: servono gli alimenti CIQUAL degli ingredienti e i pesi delle loro dosi, in Anagrafica."
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByText("Contate 0 righe su 6.")).toBeInTheDocument();
  });

  it("senza porzioni: per tutta la ricetta", async () => {
    stub([{ ...CONTO, basis: "recipe", servings: null }, 200]);
    renderPanel();

    await apri();

    expect(await screen.findByRole("table", { name: "Per tutta la ricetta: porzioni non indicate" })).toBeInTheDocument();
  });

  it("un calcolo fallito offre «Riprova a calcolarli», e rilegge", async () => {
    stub([{ detail: "ricetta inesistente" }, 404], [CONTO, 200]);
    renderPanel();

    await apri();
    expect(await screen.findByText("Non sono riuscito a calcolare i valori nutrizionali.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Riprova a calcolarli" }));

    expect(await screen.findByRole("cell", { name: "465 kcal" })).toBeInTheDocument();
  });

  it("una rilettura fallita lascia i numeri già letti", async () => {
    const spy = stub([CONTO, 200], [{ detail: "ricetta inesistente" }, 404]);
    const client = renderPanel();

    await apri();
    expect(await screen.findByRole("cell", { name: "465 kcal" })).toBeInTheDocument();
    await act(async () => {
      await client.invalidateQueries({ queryKey: ["recipe-nutrition"] });
      // il rendering segue la notifica con un giro: lo si aspetta, o l'asserzione guarda prima
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    expect(client.getQueryState(["recipe-nutrition", "r-1"])?.status).toBe("error");

    expect(spy).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("cell", { name: "465 kcal" })).toBeInTheDocument();
    expect(screen.queryByText("Non sono riuscito a calcolare i valori nutrizionali.")).toBeNull();
  });

  it("«Nascondi» richiude", async () => {
    stub([CONTO, 200]);
    renderPanel();

    await apri();
    await screen.findByRole("table");
    await userEvent.click(screen.getByRole("button", { name: "Nascondi i valori nutrizionali" }));

    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByRole("button", { name: "Mostra i valori nutrizionali" })).toBeInTheDocument();
  });
});
