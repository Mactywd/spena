import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { RecipeBookScreen } from "./RecipeBookScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";

const CARBONARA = {
  id: "r-carb", title: "Carbonara", description: null, source: "manual", missing: 0,
  cookable: true, missing_names: [], image_url: null, prep_minutes: null, cook_minutes: null,
  category: null, cost: null, archived_at: null,
};
const AGLIO = { ...CARBONARA, id: "r-aglio", title: "Aglio e olio" };
const ELIMINATA = { deletedRecipe: { id: "r-carb", title: "Carbonara" } };

type Rotta = (path: string, init?: RequestInit) => [unknown, number];

/** Le chiamate che lo schermo fa sempre hanno una risposta fissa; la ricerca e la
 * PATCH le decide il test. */
function stubFetch(route: Rotta) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    const [body, status]: [unknown, number] = path.includes("/imports/status")
      ? [{ fetched: 0, pending_recipes: 0, imported: 0, skipped: 0, pending_terms: 0 }, 200]
      : path.includes("/recipes/categories")
        ? [[], 200]
        : path.includes("/recipes/search-mode")
          ? [{ semantic: true }, 200]
          : route(path, init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** Quel che la cronologia ricorda di questa voce: la lapide non deve restarci. */
function StatoDellaVoce() {
  const location = useLocation();
  return <p data-testid="stato">{JSON.stringify(location.state)}</p>;
}

function renderBook(state: unknown = ELIMINATA) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: "/ricette", state }]}>
        <Routes>
          <Route
            path="/ricette"
            element={
              <>
                <RecipeBookScreen />
                <StatoDellaVoce />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function patchMandate(spy: ReturnType<typeof stubFetch>) {
  return spy.mock.calls
    .filter(([, init]) => init?.method === "PATCH")
    .map(([url, init]) => [String(url), JSON.parse(String(init!.body))]);
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("la lapide del ricettario (R10 §6.1)", () => {
  it("arriva con la navigazione e dice quale ricetta, anche se la ricerca la manda ancora", async () => {
    stubFetch(() => [[CARBONARA, AGLIO], 200]);
    renderBook();

    expect(await screen.findByRole("status")).toHaveTextContent("Carbonara eliminata");
    expect(await screen.findByText("Aglio e olio")).toBeInTheDocument();
    // una risposta vecchia della ricerca non la fa ricomparire sotto la sua lapide
    expect(screen.queryByRole("link", { name: /Carbonara/ })).toBeNull();
  });

  it("la cronologia la dimentica subito: un «indietro» non la resusciterebbe", async () => {
    stubFetch(() => [[AGLIO], 200]);
    renderBook();

    await screen.findByRole("status");
    await waitFor(() => expect(screen.getByTestId("stato")).toHaveTextContent("null"));
    expect(screen.getByRole("status")).toHaveTextContent("Carbonara eliminata");
  });

  it("«Annulla» la riporta nel ricettario, e la lapide se ne va", async () => {
    let eliminata = true;
    const spy = stubFetch((_path, init) => {
      if (init?.method === "PATCH") {
        eliminata = false;
        return [CARBONARA, 200];
      }
      return [eliminata ? [AGLIO] : [CARBONARA, AGLIO], 200];
    });
    renderBook();

    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));

    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
    expect(await screen.findByText("Carbonara")).toBeInTheDocument();
    expect(patchMandate(spy)).toEqual([["/api/v1/recipes/r-carb", { archived: false }]]);
  });

  it("passati i secondi dell'annulla la lapide se ne va", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    stubFetch(() => [[AGLIO], 200]);
    renderBook();

    expect(await screen.findByRole("status")).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(6000);

    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  });

  it("un annulla che fallisce lascia la lapide con l'errore, ferma, e si riprova", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const utente = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    let tentativi = 0;
    stubFetch((_path, init) => {
      if (init?.method === "PATCH") {
        tentativi += 1;
        return tentativi === 1 ? [{ detail: "no" }, 500] : [CARBONARA, 200];
      }
      return [[AGLIO], 200];
    });
    renderBook();

    await utente.click(await screen.findByRole("button", { name: "Annulla" }));
    expect(await screen.findByText(/non sono riuscito a riportarla/i)).toBeInTheDocument();

    // il timer si è spento con l'errore: la lapide non scade mentre lo mostra
    await vi.advanceTimersByTimeAsync(6000);
    expect(screen.getByRole("status")).toHaveTextContent("Carbonara eliminata");

    await utente.click(screen.getByRole("button", { name: "Annulla" }));
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  });

  it("senza una ricetta eliminata non c'è lapide", async () => {
    stubFetch(() => [[AGLIO], 200]);
    renderBook(null);

    await screen.findByText("Aglio e olio");
    expect(screen.queryByRole("status")).toBeNull();
  });
});

// jsdom non ha layout: non scorre niente e non sa dove stia un elemento. Quel che si
// può controllare qui è *a chi* si chiede di venire in vista; che ci arrivi davvero
// sotto l'intestazione fissa lo dice solo un browser vero (frontend/e2e/modifica-ricette.spec.ts).
describe("la lapide si porta in vista all'arrivo (R10 §6.1)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("arrivando con una ricetta eliminata, la lapide viene portata in cima", async () => {
    stubFetch(() => [[AGLIO], 200]);
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    renderBook();

    const tombstone = await screen.findByRole("status");
    await waitFor(() => expect(scroll).toHaveBeenCalled());
    expect(scroll.mock.contexts.at(-1)).toBe(tombstone);
    expect(scroll).toHaveBeenLastCalledWith({ block: "start", behavior: "smooth" });
  });

  it("senza una ricetta eliminata in arrivo, non scorre niente", async () => {
    stubFetch(() => [[AGLIO], 200]);
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    renderBook(null);

    await screen.findByText("Aglio e olio");
    expect(scroll).not.toHaveBeenCalled();
  });

  it("scaduta la lapide da sola, il suo sparire non fa scorrere di nuovo", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    stubFetch(() => [[AGLIO], 200]);
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    renderBook();

    await screen.findByRole("status");
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(1));
    scroll.mockClear();

    await vi.advanceTimersByTimeAsync(6000);
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
    expect(scroll).not.toHaveBeenCalled();
  });
});
