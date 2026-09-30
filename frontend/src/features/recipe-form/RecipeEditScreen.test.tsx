import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { RecipeEditScreen } from "./RecipeEditScreen";
import { RecipeDetailScreen } from "../cooking/RecipeDetailScreen";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { RecipeDetail } from "../../domain/types";

const DETAIL: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: null, source: "manual",
  missing: 1, cookable: false, missing_names: ["Basilico"], image_url: null,
  prep_minutes: null, cook_minutes: null, category: null, cost: null, archived_at: null, main_department: null,
  instructions: "Cuoci.", servings: 2, source_ref: null, scaled_to: null,
  unscalable_lines: 0, dose_lines: 1, owned_by_import: false,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "180 g",
      quantity_display: "180 g", quantity_scaled: false, note: null,
      availability: "available", satisfied: true },
    { ingredient_id: "i2", ingredient_name: "basilico", role: "primary", quantity_text: null,
      quantity_display: null, quantity_scaled: false, note: null,
      availability: "missing", satisfied: false },
  ],
};

type Rotta = (path: string, init?: RequestInit) => [unknown, number] | undefined;

function stubFetch(route: Rotta = () => undefined) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    const [body, status] =
      route(path, init) ?? (path.includes("/pantry") ? [[], 200] : [DETAIL, 200]);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderEdit(start = "/ricette/r1/modifica", prime?: (client: QueryClient) => void) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
  });
  prime?.(client);
  return render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <MemoryRouter initialEntries={[start]}>
          <Routes>
            <Route path="/ricette/:id/modifica" element={<RecipeEditScreen />} />
            <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

/** L'indietro del browser (o di Android), e dove si è arrivati. */
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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("la modifica di una ricetta (R10 §6.2)", () => {
  it("parte dalla ricetta, e una importata dice cosa succede salvando", async () => {
    stubFetch(() => [{ ...DETAIL, owned_by_import: true }, 200]);
    renderEdit();

    expect(await screen.findByDisplayValue("Pasta al pomodoro")).toBeInTheDocument();
    expect(screen.getByText(/salvando diventa tua, e l'import non la riscriverà più/i)).toBeInTheDocument();
  });

  it("una ricetta scritta qui non porta l'avviso", async () => {
    stubFetch();
    renderEdit();

    await screen.findByDisplayValue("Pasta al pomodoro");
    expect(screen.queryByText(/salvando diventa tua/i)).toBeNull();
  });

  it("salvare manda la PUT senza la riga tolta, e torna al dettaglio con «Salvata»", async () => {
    let salvata = DETAIL;
    const spy = stubFetch((path, init) => {
      if (init?.method === "PUT") {
        salvata = { ...DETAIL, missing: 0, cookable: true, missing_names: [], ingredients: [DETAIL.ingredients[0]] };
        return [salvata, 200];
      }
      if (path.endsWith("/recipes/r1")) return [salvata, 200];
      return undefined;
    });
    renderEdit();

    await screen.findByDisplayValue("Pasta al pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Togli basilico" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));

    expect(await screen.findByText("Salvata.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Salvata.");
    expect(await screen.findByRole("heading", { name: "Pasta al pomodoro" })).toBeInTheDocument();
    const put = spy.mock.calls.find(([, init]) => init?.method === "PUT")!;
    expect(String(put[0])).toBe("/api/v1/recipes/r1");
    const corpo = JSON.parse(String(put[1]!.body));
    expect(corpo.ingredients).toEqual([{ ingredient_id: "i1", role: "primary", quantity_text: "180 g" }]);
    // la provenienza non si manda: non si cambia
    expect(corpo.source).toBeUndefined();
  });

  it("dopo il salvataggio, «indietro» non riporta al modulo", async () => {
    stubFetch();
    const client = new QueryClient({
      defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
    });
    render(
      <QueryClientProvider client={client}>
        <NoticeProvider>
          <MemoryRouter initialEntries={["/ricette/r1", "/ricette/r1/modifica"]} initialIndex={1}>
            <Routes>
              <Route path="/ricette/:id/modifica" element={<RecipeEditScreen />} />
              <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
            </Routes>
            <Cronologia />
          </MemoryRouter>
        </NoticeProvider>
      </QueryClientProvider>
    );

    await screen.findByDisplayValue("Pasta al pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));
    expect(await screen.findByText("Salvata.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "torna indietro" }));

    expect(screen.getByTestId("posizione")).toHaveTextContent(/^\/ricette\/r1$/);
    expect(screen.queryByRole("button", { name: "Salva le modifiche" })).toBeNull();
  });

  it("«Salvata» sta sopra la ricetta salvata, anche mentre il dettaglio rilegge", async () => {
    // la risposta della PUT è la ricetta a 1×: il dettaglio la mostra subito, invece di
    // mostrare la versione di prima sotto «Salvata» finché la rilettura non torna
    let saved = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown, init?: RequestInit) => {
        const path = String(url);
        if (path.includes("/pantry")) return Promise.resolve(new Response("[]", { status: 200 }));
        if (init?.method === "PUT") {
          saved = true;
          const body = { ...DETAIL, title: "Pasta al sugo" };
          return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
        }
        // dopo il salvataggio la rilettura non torna mai: si vede solo la risposta della PUT
        if (saved) return new Promise<Response>(() => {});
        return Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }));
      })
    );
    renderEdit();

    const titolo = await screen.findByDisplayValue("Pasta al pomodoro");
    await userEvent.clear(titolo);
    await userEvent.type(titolo, "Pasta al sugo");
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));

    expect(await screen.findByText("Salvata.")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Pasta al sugo" })).toBeInTheDocument();
  });

  it("dopo porzioni cambiate nel dettaglio e un costo cambiato sul server, il modulo parte dal costo salvato", async () => {
    // Il dettaglio a 3 porzioni ha la chiave ["recipe", id, 3], e la copia a 1× in cache
    // è quella letta all'apertura. Se nel frattempo il costo cambia sul server (da un
    // altro telefono), la PUT rimpiazza la ricetta intera: un modulo costruito sulla
    // copia vecchia rimanderebbe il costo di prima, zitto. Il costo dal dettaglio non si
    // cambia più (T3 Consegna 5), ma il modulo nasce ancora da una lettura fresca.
    let cost = 2;
    const spy = stubFetch((path, init) => {
      if (path.includes("/pantry")) return undefined;
      if (init?.method === "PUT") return [{ ...DETAIL, ...JSON.parse(String(init.body)), ingredients: DETAIL.ingredients }, 200];
      return [{ ...DETAIL, cost }, 200];
    });
    renderEdit("/ricette/r1");

    await screen.findByRole("heading", { name: "Pasta al pomodoro" });
    await userEvent.click(screen.getByRole("button", { name: "Una porzione in più" }));
    await waitFor(() =>
      expect(spy.mock.calls.some(([url]) => String(url).includes("servings=3"))).toBe(true)
    );
    // il costo cambia sul server, non da qui
    cost = 4;

    await userEvent.click(screen.getByRole("link", { name: "Modifica" }));
    await screen.findByDisplayValue("Pasta al pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));

    await screen.findByText("Salvata.");
    const put = spy.mock.calls.find(([, init]) => init?.method === "PUT")!;
    expect(JSON.parse(String(put[1]!.body)).cost).toBe(4);
  });

  it("con una copia in cache e la rilettura fallita, dice l'errore e non costruisce il modulo sulla copia", async () => {
    stubFetch((path) => (path.includes("/recipes/r1") ? [{ detail: "boom" }, 500] : undefined));
    renderEdit("/ricette/r1/modifica", (client) =>
      client.setQueryData(["recipe", "r1", null], { ...DETAIL, cost: 2 })
    );

    // mentre rilegge, il modulo non c'è ancora
    expect(screen.getByText("Carico…")).toBeInTheDocument();
    expect(
      await screen.findByText(/Non sono riuscito a caricare questa ricetta/, {}, { timeout: 8000 })
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Salva le modifiche" })).toBeNull();
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
  }, 10000);

  it("una ricetta che non c'è più lo dice subito, e riporta al ricettario", async () => {
    stubFetch((path) =>
      path.includes("/recipes/r1") ? [{ detail: "ricetta inesistente" }, 404] : undefined
    );
    // `renderEdit` usa il predicato vero dell'app: un 404 ritentato arriverebbe dopo 3 s,
    // fuori dal secondo che `findBy` aspetta
    renderEdit();

    expect(await screen.findByText("Questa ricetta non c'è più.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Torna al ricettario" })).toHaveAttribute("href", "/ricette");
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Salva le modifiche" })).toBeNull();
    // e anche il ritorno in alto porta al ricettario, non alla ricetta che non c'è
    expect(screen.getByRole("link", { name: "Ricette" })).toHaveAttribute("href", "/ricette");
    expect(screen.queryByRole("link", { name: "Ricetta" })).toBeNull();
  });

  it("una ricetta eliminata non si modifica: dice dove ripristinarla", async () => {
    stubFetch(() => [{ ...DETAIL, archived_at: "2026-09-28T10:00:00Z" }, 200]);
    renderEdit();

    expect(await screen.findByText(/ripristinala dalla sua pagina/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Vai alla ricetta" })).toHaveAttribute("href", "/ricette/r1");
    expect(screen.queryByRole("button", { name: "Salva le modifiche" })).toBeNull();
  });

  it("se nel frattempo è stata eliminata, il rifiuto lo dice con le sue parole", async () => {
    stubFetch((_path, init) =>
      init?.method === "PUT"
        ? [{ detail: "Questa ricetta è stata eliminata: ripristinala prima di modificarla." }, 409]
        : undefined
    );
    renderEdit();

    await screen.findByDisplayValue("Pasta al pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Questa ricetta è stata eliminata: ripristinala prima di modificarla."
    );
  });
});
