import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider, type InfiniteData } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { useArchiveRecipe, withoutRecipe } from "./useArchiveRecipe";
import type { RecipePage } from "./api";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { RecipeSummary } from "../../domain/types";

const CARBONARA: RecipeSummary = {
  id: "r-carb", title: "Carbonara", description: null, source: "manual", missing: 0,
  cookable: true, missing_names: [], image_url: null, prep_minutes: null, cook_minutes: null,
  category: null, cost: null, archived_at: null, main_department: null,
};
const AGLIO: RecipeSummary = { ...CARBONARA, id: "r-aglio", title: "Aglio e olio" };

// una voce del ricettario in cache, com'è la chiave di RecipeBookScreen
const CHIAVE = ["recipes", "", null, "", []];

function pagine(): InfiniteData<RecipePage> {
  return {
    pages: [{ recipes: [CARBONARA, AGLIO], total: 2, totalIsLowerBound: false }],
    pageParams: [0],
  };
}

function nuovoClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

type Rotta = (path: string, init?: RequestInit) => [unknown, number];

function stubFetch(route: Rotta) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function patchMandate(spy: ReturnType<typeof stubFetch>) {
  return spy.mock.calls
    .filter(([, init]) => init?.method === "PATCH")
    .map(([url, init]) => [String(url), JSON.parse(String(init!.body))]);
}

/** Chi elimina: un pulsante, dove si trova, e se l'eliminazione è in volo. */
function Prova() {
  const { archive, pending } = useArchiveRecipe();
  const location = useLocation();
  return (
    <>
      <p data-testid="dove">{location.pathname}</p>
      <p data-testid="in-volo">{String(pending)}</p>
      <button type="button" onClick={() => archive({ id: CARBONARA.id, title: CARBONARA.title })}>
        elimina
      </button>
    </>
  );
}

// NoticeProvider sopra il router, come in App.tsx: l'avviso sopravvive al cambio di pagina
function renderProva(client = nuovoClient()) {
  return render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <MemoryRouter initialEntries={["/ricette/r-carb"]}>
          <Routes>
            <Route path="*" element={<Prova />} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useArchiveRecipe", () => {
  it("archivia, toglie la ricetta dal ricettario in cache, avvisa con «Annulla» e porta al ricettario", async () => {
    const spy = stubFetch(() => [{}, 200]);
    const client = nuovoClient();
    client.setQueryData(CHIAVE, pagine());
    renderProva(client);

    await userEvent.click(screen.getByRole("button", { name: "elimina" }));

    expect(await screen.findByText("Eliminata: Carbonara")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Annulla" })).toBeInTheDocument();
    expect(screen.getByTestId("dove")).toHaveTextContent(/^\/ricette$/);
    expect(patchMandate(spy)).toEqual([["/api/v1/recipes/r-carb", { archived: true }]]);
    // una pagina in cache non la mostra più, e il totale la conta una volta in meno
    expect(client.getQueryData<InfiniteData<RecipePage>>(CHIAVE)!.pages[0]).toEqual({
      recipes: [AGLIO],
      total: 1,
      totalIsLowerBound: false,
    });
  });

  it("«Annulla» la rimette nel ricettario", async () => {
    const spy = stubFetch(() => [{}, 200]);
    renderProva();

    await userEvent.click(screen.getByRole("button", { name: "elimina" }));
    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));

    await waitFor(() =>
      expect(patchMandate(spy)).toEqual([
        ["/api/v1/recipes/r-carb", { archived: true }],
        ["/api/v1/recipes/r-carb", { archived: false }],
      ])
    );
    expect(screen.queryByText("Eliminata: Carbonara")).toBeNull();
    expect(screen.queryByText(/Non sono riuscito/)).toBeNull();
  });

  it("un «Annulla» che fallisce lo dice, e «Riprova» ci riprova", async () => {
    let ripristini = 0;
    const spy = stubFetch((_path, init) => {
      const { archived } = JSON.parse(String(init!.body)) as { archived: boolean };
      if (archived) return [{}, 200];
      ripristini += 1;
      return ripristini === 1 ? [{ detail: "giù" }, 500] : [{}, 200];
    });
    renderProva();

    await userEvent.click(screen.getByRole("button", { name: "elimina" }));
    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));
    // la ricetta è eliminata davvero: perdere l'annulla qui sarebbe il vicolo cieco
    expect(
      await screen.findByText("Non sono riuscito a riportare «Carbonara» nel ricettario.")
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));

    await waitFor(() => expect(ripristini).toBe(2));
    await waitFor(() => expect(screen.queryByText(/Non sono riuscito a riportare/)).toBeNull());
    expect(patchMandate(spy)).toHaveLength(3);
  });

  it("un'eliminazione che fallisce lascia la ricetta dov'è, e «Riprova» ci riprova", async () => {
    let tentativi = 0;
    const spy = stubFetch(() => {
      tentativi += 1;
      return tentativi === 1 ? [{ detail: "giù" }, 500] : [{}, 200];
    });
    const client = nuovoClient();
    client.setQueryData(CHIAVE, pagine());
    renderProva(client);

    await userEvent.click(screen.getByRole("button", { name: "elimina" }));

    expect(
      await screen.findByText("Non sono riuscito a eliminarla: è ancora nel ricettario.")
    ).toBeInTheDocument();
    expect(screen.getByTestId("dove")).toHaveTextContent("/ricette/r-carb");
    expect(client.getQueryData<InfiniteData<RecipePage>>(CHIAVE)!.pages[0].recipes).toHaveLength(2);

    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));

    expect(await screen.findByText("Eliminata: Carbonara")).toBeInTheDocument();
    expect(screen.getByTestId("dove")).toHaveTextContent(/^\/ricette$/);
    expect(patchMandate(spy)).toHaveLength(2);
  });

  it("mentre elimina è in volo, e poi non più", async () => {
    let rispondi: (risposta: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => { rispondi = resolve; }))
    );
    renderProva();
    expect(screen.getByTestId("in-volo")).toHaveTextContent("false");

    await userEvent.click(screen.getByRole("button", { name: "elimina" }));
    await waitFor(() => expect(screen.getByTestId("in-volo")).toHaveTextContent("true"));

    rispondi(new Response(JSON.stringify({}), { status: 200 }));
    await waitFor(() => expect(screen.getByTestId("in-volo")).toHaveTextContent("false"));
  });
});

describe("withoutRecipe", () => {
  it("toglie la ricetta da ogni pagina, e il totale la conta una volta in meno", () => {
    const due: InfiniteData<RecipePage> = {
      pages: [
        { recipes: [CARBONARA, AGLIO], total: 3, totalIsLowerBound: false },
        { recipes: [{ ...AGLIO, id: "r-altra" }], total: 3, totalIsLowerBound: false },
      ],
      pageParams: [0, 2],
    };
    expect(withoutRecipe(due, "r-carb")).toEqual({
      pages: [
        { recipes: [AGLIO], total: 2, totalIsLowerBound: false },
        { recipes: [{ ...AGLIO, id: "r-altra" }], total: 2, totalIsLowerBound: false },
      ],
      pageParams: [0, 2],
    });
  });

  it("se la ricetta non c'è, le pagine restano le stesse", () => {
    const dati = pagine();
    expect(withoutRecipe(dati, "r-sconosciuta")).toBe(dati);
  });

  it("non tocca `totalIsLowerBound`: un minimo del server resta un minimo", () => {
    const conMinimo: InfiniteData<RecipePage> = {
      pages: [{ recipes: [CARBONARA, AGLIO], total: 5, totalIsLowerBound: true }],
      pageParams: [0],
    };
    expect(withoutRecipe(conMinimo, "r-carb")!.pages[0]).toEqual({
      recipes: [AGLIO],
      total: 4,
      totalIsLowerBound: true,
    });
  });

  it("senza pagine, o senza totale, non inventa niente", () => {
    expect(withoutRecipe(undefined, "r-carb")).toBeUndefined();
    const senzaTotale: InfiniteData<RecipePage> = {
      pages: [{ recipes: [CARBONARA], total: null, totalIsLowerBound: false }],
      pageParams: [0],
    };
    expect(withoutRecipe(senzaTotale, "r-carb")!.pages[0]).toEqual({
      recipes: [],
      total: null,
      totalIsLowerBound: false,
    });
  });
});
