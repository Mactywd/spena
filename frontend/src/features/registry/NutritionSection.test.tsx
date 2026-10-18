import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { IngredientScreen } from "./IngredientScreen";
import { NutritionSection } from "./NutritionSection";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { CiqualFood, IngredientNutrition } from "./nutrition";
import type { IngredientDetail } from "../../domain/types";

const CITAZIONE = "Anses. 2025. Table de composition nutritionnelle des aliments Ciqual";
const DA_DECIDERE: IngredientNutrition = {
  state: "undecided", decided_by: null, food: null, nutrients: [], source: "CIQUAL 2025", citation: CITAZIONE,
};
const TROVATI: CiqualFood[] = [
  { code: "90001", name_fr: "Tomate, crue", group_fr: "légumes" },
  { code: "90002", name_fr: "Tomate, concentré", group_fr: "légumes" },
];
const POMODORO: IngredientNutrition = {
  state: "food",
  decided_by: "ai",
  food: TROVATI[0],
  nutrients: [
    { key: "kcal", label: "Energia", unit: "kcal", main: true, value: 18 },
    { key: "protein", label: "Proteine", unit: "g", main: true, value: 0.86 },
    { key: "fiber", label: "Fibre", unit: "g", main: true, value: null },
    { key: "vitamin_c", label: "Vitamina C", unit: "mg", main: false, value: 14 },
  ],
  source: "CIQUAL 2025",
  citation: CITAZIONE,
};
const NESSUNO: IngredientNutrition = { ...DA_DECIDERE, state: "none", decided_by: "human" };

type FetchRoute = (path: string, init?: RequestInit) => [unknown, number];
type RouteOverride = (path: string, init?: RequestInit) => [unknown, number] | undefined;

function stub(route: FetchRoute) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    return Promise.resolve(
      status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status })
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function chiamate(spy: ReturnType<typeof stub>, metodo: string, pezzo: string) {
  return spy.mock.calls.filter(
    ([url, init]) =>
      String(url).includes(pezzo) && ((init as RequestInit | undefined)?.method ?? "GET") === metodo
  );
}

/** Le risposte di sempre: lo stato dato, la ricerca che trova i due pomodori. */
function rotte(stato: IngredientNutrition, altro?: RouteOverride): FetchRoute {
  return (path, init) => {
    const risposta = altro?.(path, init);
    if (risposta) return risposta;
    if (path.includes("/ciqual/foods")) return [TROVATI, 200];
    if (path.endsWith("/ingredients/i-pomodoro/nutrition")) return [stato, 200];
    return [{}, 404];
  };
}

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: defaultQueryRetryPredicate } } });
}

function renderSection() {
  render(
    <QueryClientProvider client={client()}>
      <NutritionSection ingredientId="i-pomodoro" />
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("NutritionSection", () => {
  it("non ancora abbinato: lo dice, offre «Scegli l'alimento», e cita la fonte", async () => {
    stub(rotte(DA_DECIDERE));
    renderSection();

    expect(
      await screen.findByText(
        "Non ancora abbinato a un alimento della tabella CIQUAL: lo farà l'AI al prossimo giro, oppure sceglilo tu."
      )
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Scegli l'alimento" })).toBeInTheDocument();
    expect(
      screen.getByText("Fonte: Anses, Table de composition nutritionnelle des aliments Ciqual 2025.")
    ).toBeInTheDocument();
  });

  it("un alimento: il nome, la provenienza, la tabella per 100 g", async () => {
    stub(rotte(POMODORO));
    renderSection();

    expect(await screen.findByText("Tomate, crue")).toBeInTheDocument();
    expect(screen.getByText("CIQUAL 2025 · 90001 · scelto dall'AI")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Per 100 g" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "18 kcal" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "0,86 g" })).toBeInTheDocument();
    expect(screen.getByText("Vitamine e minerali (1)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cambia alimento" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Annulla la scelta" })).toBeInTheDocument();
  });

  it("nessun alimento adatto: lo dice, con chi l'ha scelto, e niente tabella", async () => {
    stub(rotte(NESSUNO));
    renderSection();

    expect(await screen.findByText("Nessun alimento adatto")).toBeInTheDocument();
    expect(screen.getByText("CIQUAL 2025 · scelto a mano")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("«Annulla la scelta» manda la DELETE e dice che torna all'AI", async () => {
    const spy = stub(
      rotte(POMODORO, (_path, init) => (init?.method === "DELETE" ? [DA_DECIDERE, 200] : undefined))
    );
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Annulla la scelta" }));

    expect(
      await screen.findByText("Scelta annullata: l'AI lo abbinerà al prossimo giro.")
    ).toBeInTheDocument();
    expect(chiamate(spy, "DELETE", "/ingredients/i-pomodoro/nutrition")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Scegli l'alimento" })).toBeInTheDocument();
  });

  it("la ricerca: si sceglie un alimento e si salva con la PUT", async () => {
    const scelto: IngredientNutrition = { ...POMODORO, food: TROVATI[1], decided_by: "human" };
    const spy = stub(rotte(POMODORO, (_path, init) => (init?.method === "PUT" ? [scelto, 200] : undefined)));
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Cambia alimento" }));
    await userEvent.type(screen.getByLabelText("Cerca nella tabella CIQUAL"), "tom");
    await userEvent.click(await screen.findByRole("radio", { name: "Tomate, concentré" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva l'alimento" }));

    expect(await screen.findByText("CIQUAL 2025 · 90002 · scelto a mano")).toBeInTheDocument();
    expect(screen.queryByLabelText("Cerca nella tabella CIQUAL")).toBeNull();
    const [, init] = chiamate(spy, "PUT", "/ingredients/i-pomodoro/nutrition")[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ ciqual_code: "90002" });
    expect(chiamate(spy, "GET", "/ciqual/foods?q=tom").length).toBeGreaterThan(0);
  });

  it("«Salva l'alimento» non ancora: senza una scelta, e sull'alimento che ha già", async () => {
    stub(rotte(POMODORO));
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Cambia alimento" }));
    const salva = screen.getByRole("button", { name: "Salva l'alimento" });
    expect(salva).toHaveAttribute("aria-disabled", "true");
    expect(salva).toHaveAccessibleDescription("Scegli un alimento dall'elenco.");

    await userEvent.type(screen.getByLabelText("Cerca nella tabella CIQUAL"), "tom");
    await userEvent.click(await screen.findByRole("radio", { name: "Tomate, crue" }));
    expect(screen.getByRole("button", { name: "Salva l'alimento" })).toHaveAccessibleDescription(
      "È già il suo alimento: scegline un altro."
    );
  });

  it("«Nessun alimento adatto» manda la PUT con il codice vuoto", async () => {
    const spy = stub(rotte(DA_DECIDERE, (_path, init) => (init?.method === "PUT" ? [NESSUNO, 200] : undefined)));
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Scegli l'alimento" }));
    await userEvent.click(screen.getByRole("button", { name: "Nessun alimento adatto" }));

    expect(await screen.findByText("CIQUAL 2025 · scelto a mano")).toBeInTheDocument();
    const [, init] = chiamate(spy, "PUT", "/ingredients/i-pomodoro/nutrition")[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ ciqual_code: null });
  });

  it("un rifiuto si legge col suo perché, e la ricerca resta aperta", async () => {
    const rifiuto = { code: "unknown_food", detail: "Questo alimento non è nella tabella CIQUAL caricata: cercane un altro." };
    stub(rotte(DA_DECIDERE, (_path, init) => (init?.method === "PUT" ? [rifiuto, 409] : undefined)));
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Scegli l'alimento" }));
    await userEvent.click(screen.getByRole("button", { name: "Nessun alimento adatto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(rifiuto.detail);
    expect(screen.getByLabelText("Cerca nella tabella CIQUAL")).toBeInTheDocument();
  });

  it("un guasto del salvataggio dice di riprovare", async () => {
    stub(rotte(DA_DECIDERE, (_path, init) => (init?.method === "PUT" ? [{ detail: "x" }, 500] : undefined)));
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Scegli l'alimento" }));
    await userEvent.click(screen.getByRole("button", { name: "Nessun alimento adatto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Non sono riuscito a salvare la scelta. Riprova."
    );
  });

  it("una ricerca senza risultati dice come cercare", async () => {
    stub(rotte(DA_DECIDERE, (path) => (path.includes("/ciqual/foods") ? [[], 200] : undefined)));
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Scegli l'alimento" }));
    await userEvent.type(screen.getByLabelText("Cerca nella tabella CIQUAL"), "zzz");

    expect(
      await screen.findByText("Nessun alimento trovato: prova un'altra parola, in francese.")
    ).toBeInTheDocument();
  });

  it("«Lascia com'è» chiude la ricerca senza scrivere", async () => {
    const spy = stub(rotte(POMODORO));
    renderSection();

    await userEvent.click(await screen.findByRole("button", { name: "Cambia alimento" }));
    await userEvent.click(screen.getByRole("button", { name: "Lascia com'è" }));

    expect(screen.queryByLabelText("Cerca nella tabella CIQUAL")).toBeNull();
    expect(screen.getByText("Tomate, crue")).toBeInTheDocument();
    expect(chiamate(spy, "PUT", "/nutrition")).toHaveLength(0);
  });

  it("una lettura fallita offre «Riprova a leggerli», e rilegge", async () => {
    let letture = 0;
    stub((path) => {
      if (!path.endsWith("/ingredients/i-pomodoro/nutrition")) return [{}, 404];
      letture += 1;
      return letture === 1 ? [{ detail: "ingrediente inesistente" }, 404] : [DA_DECIDERE, 200];
    });
    renderSection();

    expect(
      await screen.findByText("Non sono riuscito a leggere i valori nutrizionali.")
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Riprova a leggerli" }));

    expect(await screen.findByRole("button", { name: "Scegli l'alimento" })).toBeInTheDocument();
  });
});

describe("la sezione nella scheda dell'ingrediente", () => {
  function scheda(kind: "food" | "non_food"): IngredientDetail {
    return {
      id: "i-pomodoro", name: "pomodoro", display_name: "Pomodoro", category: kind === "food" ? "verdura" : "casa",
      kind, aliases: [], products: [], usage: { recipes: 0, pantry: 0, shopping: 0 },
    };
  }

  function renderScheda() {
    render(
      <QueryClientProvider client={client()}>
        <MemoryRouter initialEntries={["/anagrafica/ingrediente/i-pomodoro"]}>
          <Routes>
            <Route path="/anagrafica/ingrediente/:id" element={<IngredientScreen />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  it("un alimento ha «Valori nutrizionali», in fondo dopo «Prodotti»", async () => {
    stub(rotte(POMODORO, (path) => (path.endsWith("/ingredients/i-pomodoro") ? [scheda("food"), 200] : undefined)));
    renderScheda();

    const titolo = await screen.findByRole("heading", { name: "Valori nutrizionali" });
    const prodotti = screen.getByRole("heading", { name: "Prodotti" });
    expect(prodotti.compareDocumentPosition(titolo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(await screen.findByText("Tomate, crue")).toBeInTheDocument();
  });

  it("una voce non alimentare non ha la sezione, e non la chiede", async () => {
    const spy = stub(
      rotte(POMODORO, (path) => (path.endsWith("/ingredients/i-pomodoro") ? [scheda("non_food"), 200] : undefined))
    );
    renderScheda();

    await screen.findByRole("heading", { name: "Pomodoro" });
    await waitFor(() => expect(screen.getByRole("heading", { name: "Prodotti" })).toBeInTheDocument());
    expect(screen.queryByRole("heading", { name: "Valori nutrizionali" })).toBeNull();
    expect(chiamate(spy, "GET", "/nutrition")).toHaveLength(0);
  });
});
