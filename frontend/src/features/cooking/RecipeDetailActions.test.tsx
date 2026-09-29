import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { RecipeDetailScreen } from "./RecipeDetailScreen";
import { RecipeBookScreen } from "../recipes/RecipeBookScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { RecipeDetail } from "../../domain/types";

const DETAIL: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: null, source: "manual",
  missing: 0, cookable: true, missing_names: [], image_url: null, prep_minutes: null,
  cook_minutes: null, category: null, cost: null, archived_at: null, main_department: null,
  instructions: "Cuoci.", servings: 2, source_ref: null, scaled_to: null,
  unscalable_lines: 0, dose_lines: 1, owned_by_import: false,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "180 g",
      quantity_display: "180 g", quantity_scaled: false, note: null,
      availability: "available", satisfied: true },
  ],
};

type Rotta = (path: string, init?: RequestInit) => [unknown, number] | undefined;

/** Il test decide le risposte che gli interessano; le altre chiamate dei due schermi
 * hanno una risposta fissa. */
function stubFetch(route: Rotta = () => undefined) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    const [body, status] = route(path, init) ??
      (path.includes("/pantry")
        ? [[], 200]
        : path.includes("/imports/status")
          ? [{ fetched: 0, pending_recipes: 0, imported: 0, skipped: 0, pending_terms: 0 }, 200]
          : path.includes("/recipes/categories") || path.includes("/recipes/search?")
            ? [[], 200]
            : path.includes("/recipes/search-mode")
              ? [{ semantic: true }, 200]
              : [DETAIL, 200]);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** Quel che la cronologia ricorda di questa voce: «Salvata» non deve restarci. */
function StatoDellaVoce() {
  const location = useLocation();
  return <p data-testid="stato">{JSON.stringify(location.state)}</p>;
}

function renderAt(
  entry: string | { pathname: string; state: unknown },
  { notice = false }: { notice?: boolean } = {}
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
  });
  const albero = (
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/ricette" element={<RecipeBookScreen />} />
        <Route
          path="/ricette/:id"
          element={
            <>
              <RecipeDetailScreen />
              <StatoDellaVoce />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  );
  return render(
    <QueryClientProvider client={client}>
      {notice ? <NoticeProvider>{albero}</NoticeProvider> : albero}
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
  vi.restoreAllMocks();
});

describe("le azioni del dettaglio (R10 §6.1)", () => {
  it("«Modifica» porta al modulo, «Elimina» gli sta accanto", async () => {
    stubFetch();
    renderAt("/ricette/r1");

    expect(await screen.findByRole("link", { name: "Modifica" })).toHaveAttribute(
      "href", "/ricette/r1/modifica"
    );
    expect(screen.getByRole("button", { name: "Elimina" })).toBeInTheDocument();
  });

  it("«Elimina» archivia subito e torna al ricettario con l'avviso", async () => {
    const spy = stubFetch((_path, init) =>
      init?.method === "PATCH" ? [{ ...DETAIL, archived_at: "2026-09-28T10:00:00Z" }, 200] : undefined
    );
    renderAt("/ricette/r1", { notice: true });

    await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));

    expect(await screen.findByText("Eliminata: Pasta al pomodoro")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Annulla" })).toBeInTheDocument();
    // si è tornati al ricettario
    expect(await screen.findByLabelText("Cerca nel ricettario")).toBeInTheDocument();
    expect(patchMandate(spy)).toEqual([["/api/v1/recipes/r1", { archived: true }]]);
  });

  it("dopo «Elimina», «indietro» non riporta alla ricetta eliminata", async () => {
    stubFetch((_path, init) =>
      init?.method === "PATCH" ? [{ ...DETAIL, archived_at: "2026-09-28T10:00:00Z" }, 200] : undefined
    );
    function Cronologia() {
      const navigate = useNavigate();
      const location = useLocation();
      return (
        <>
          <p data-testid="posizione">{location.pathname}</p>
          <button type="button" onClick={() => navigate(-1)}>
            torna indietro
          </button>
        </>
      );
    }
    const client = new QueryClient({
      defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
    });
    render(
      <QueryClientProvider client={client}>
        <NoticeProvider>
          <MemoryRouter initialEntries={["/ricette", "/ricette/r1"]} initialIndex={1}>
            <Routes>
              <Route path="/ricette" element={<RecipeBookScreen />} />
              <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
            </Routes>
            <Cronologia />
          </MemoryRouter>
        </NoticeProvider>
      </QueryClientProvider>
    );

    await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));
    expect(await screen.findByText("Eliminata: Pasta al pomodoro")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "torna indietro" }));

    expect(screen.getByTestId("posizione")).toHaveTextContent(/^\/ricette$/);
    expect(screen.queryByText("Questa ricetta è stata eliminata.")).toBeNull();
  });

  it("un'eliminazione che fallisce lo dice, e la ricetta resta lì", async () => {
    stubFetch((_path, init) => (init?.method === "PATCH" ? [{ detail: "no" }, 500] : undefined));
    renderAt("/ricette/r1", { notice: true });

    await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));

    expect(await screen.findByText(/non sono riuscito a eliminarla/i)).toBeInTheDocument();
    // l'avviso offre di riprovare: la ricetta c'è ancora, e il gesto anche
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pasta al pomodoro" })).toBeInTheDocument();
  });

  it("una ricetta eliminata aperta da un collegamento offre «Ripristina» e nient'altro", async () => {
    let eliminata = true;
    const spy = stubFetch((path, init) => {
      if (init?.method === "PATCH") {
        eliminata = false;
        return [DETAIL, 200];
      }
      if (path.endsWith("/recipes/r1"))
        return [{ ...DETAIL, archived_at: eliminata ? "2026-09-28T10:00:00Z" : null }, 200];
      return undefined;
    });
    renderAt("/ricette/r1");

    expect(await screen.findByText("Questa ricetta è stata eliminata.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cucina" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Modifica" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Elimina" })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Ripristina" }));

    expect(await screen.findByRole("button", { name: "Cucina" })).toBeInTheDocument();
    expect(patchMandate(spy)).toEqual([["/api/v1/recipes/r1", { archived: false }]]);
  });

  it("dopo un salvataggio dice «Salvata» e lo porta in vista", async () => {
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    stubFetch();
    renderAt({ pathname: "/ricette/r1", state: { saved: true } });

    const esito = await screen.findByRole("status");
    expect(esito).toHaveTextContent("Salvata.");
    await vi.waitFor(() => expect(scroll.mock.contexts).toContain(esito));
    // la cronologia lo dimentica subito: un «indietro» e un «avanti» non lo ridicono
    await vi.waitFor(() => expect(screen.getByTestId("stato")).toHaveTextContent("null"));
    expect(screen.getByRole("status")).toHaveTextContent("Salvata.");
  });
});
