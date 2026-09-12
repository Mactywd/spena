import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ImportQueueScreen } from "./ImportQueueScreen";

const TERMINI = [
  {
    id: "t1",
    display_name: "Rigatoni",
    occurrences: 12,
    suggestion: { ingredient_id: "i1", name: "pasta", certain: false },
    waiting_titles: ["Pasta alla norma", "Pasta al forno"],
  },
  {
    id: "t2",
    display_name: "Acqua",
    occurrences: 7,
    suggestion: null,
    waiting_titles: ["Pane casereccio"],
  },
];

const PROPOSTE = {
  proposals: [
    { term_id: "t1", action: "map", ingredient_id: "i1", name: null,
      display_name: null, category: null },
    { term_id: "t2", action: "ignore", ingredient_id: null, name: null,
      display_name: null, category: null },
  ],
};

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ImportQueueScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

/** Un fetch che risponde in base al percorso e al metodo: la schermata fa tre
 * chiamate diverse, e il corpo di una Response si legge una volta sola. */
function stubFetch(route: (path: string, method: string) => [unknown, number]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init?.method ?? "GET");
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

const CODA_NORMALE = (path: string, method: string): [unknown, number] => {
  if (path.includes("/imports/terms/proposals")) return [PROPOSTE, 200];
  if (path.includes("/imports/terms") && method === "POST")
    return [{ unlocked: 12, remaining_terms: 1 }, 200];
  if (path.includes("/imports/terms")) return [TERMINI, 200];
  if (path.includes("/imports/status"))
    return [
      { fetched: 20, pending_recipes: 19, imported: 1, skipped: 0, pending_terms: 2 },
      200,
    ];
  return [{}, 404];
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("coda di revisione dell'import", () => {
  it("mostra il termine, quante ricette aspettano e qualche titolo", async () => {
    stubFetch(CODA_NORMALE);
    renderScreen();

    expect(await screen.findByText("Rigatoni")).toBeInTheDocument();
    expect(screen.getByText(/12 ricette in attesa/)).toBeInTheDocument();
    expect(screen.getByText(/Pasta alla norma/)).toBeInTheDocument();
  });

  it("la proposta di Claude diventa un pulsante che dice cosa farà", async () => {
    stubFetch(CODA_NORMALE);
    renderScreen();

    expect(
      await screen.findByRole("button", { name: /Collega a pasta/i })
    ).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /^Ignora «Acqua»$/ })).toBeInTheDocument();
  });

  it("confermare la proposta manda la decisione e dice quante ricette ha sbloccato", async () => {
    const spy = stubFetch(CODA_NORMALE);
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: /Collega a pasta/i }));

    await waitFor(() => expect(screen.getByText(/Sbloccate 12 ricette/)).toBeInTheDocument());
    const decisione = spy.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/imports/terms/t1/decision") &&
        (init as RequestInit | undefined)?.method === "POST"
    );
    expect(JSON.parse(String((decisione?.[1] as RequestInit).body))).toEqual({
      action: "map",
      ingredient_id: "i1",
    });
  });

  it("ignorare un termine lo manda come tale", async () => {
    const spy = stubFetch(CODA_NORMALE);
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: /^Ignora «Acqua»$/ }));

    await waitFor(() => {
      const inviata = spy.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/imports/terms/t2/decision") &&
          (init as RequestInit | undefined)?.method === "POST"
      );
      expect(JSON.parse(String((inviata?.[1] as RequestInit).body))).toEqual({
        action: "ignore",
      });
    });
  });

  it("senza le proposte la coda funziona e lo dichiara", async () => {
    stubFetch((path, method) => {
      if (path.includes("/imports/terms/proposals")) return [{ detail: "no" }, 503];
      return CODA_NORMALE(path, method);
    });
    renderScreen();

    expect(await screen.findByText("Rigatoni")).toBeInTheDocument();
    expect(screen.getByText(/decidi a mano/i)).toBeInTheDocument();
    // il suggerimento testuale resta, ed è l'altra via per decidere in un tocco
    expect(await screen.findByRole("button", { name: /Collega a pasta/i })).toBeInTheDocument();
  });

  it("a coda vuota dice che non c'è niente da fare", async () => {
    stubFetch((path) => {
      if (path.includes("/imports/terms/proposals")) return [{ proposals: [] }, 200];
      if (path.includes("/imports/terms")) return [[], 200];
      return [
        { fetched: 20, pending_recipes: 0, imported: 20, skipped: 0, pending_terms: 0 },
        200,
      ];
    });
    renderScreen();

    expect(await screen.findByText(/Niente da abbinare/i)).toBeInTheDocument();
  });

  it("se la coda non risponde lo dice insieme a cosa resta possibile", async () => {
    stubFetch((path) => {
      if (path.includes("/imports/terms")) return [{ detail: "rotto" }, 500];
      return [{}, 500];
    });
    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent(/ricettario/i);
  });
});
