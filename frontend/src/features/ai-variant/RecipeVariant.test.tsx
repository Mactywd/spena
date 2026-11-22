import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { createTestQueryClient } from "../../test/queryClient";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { RecipeDetailScreen } from "../cooking/RecipeDetailScreen";
import { RecipeVariantScreen } from "./RecipeVariantScreen";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { RecipeDetail, RecipeDraft } from "../../domain/types";
import type { VariantState } from "./variantState";

const ORIGINALE: RecipeDetail = {
  version: "v1", id: "r1", title: "Pasta al pomodoro", description: null, source: "manual",
  missing: 0, cookable: true, missing_names: [], image_url: null, prep_minutes: null,
  cook_minutes: null, category: "Primi piatti", cost: 1, archived_at: null, main_department: null,
  instructions: "Cuoci.", servings: 2, source_ref: null, scaled_to: null,
  unscalable_lines: 0, dose_lines: 1, anchor: null, owned_by_import: false, derived_from: null,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "180 g",
      quantity_display: "180 g", quantity_scaled: false, anchorable: true, anchor_unit: "g", note: null,
      availability: "available", satisfied: true },
  ],
};

const VARIANTE: RecipeDetail = {
  ...ORIGINALE, id: "r2", title: "Pasta al pomodoro senza basilico", source: "ai",
  source_ref: "prompt: senza basilico",
  derived_from: { id: "r1", title: "Pasta al pomodoro", archived: false },
};

const PROPOSTA: RecipeDraft = {
  title: "Pasta al pomodoro senza basilico", description: null,
  instructions: "1. Cuoci la pasta.\n2. Condisci.", servings: 2, cost: 1,
  ingredients: [
    { raw_name: "pasta", role: "primary", quantity_text: "200 g", ingredient_id: "i1",
      matched_name: "pasta", confident: true, proposed_category: null },
  ],
};

type Rotta = (path: string, init?: RequestInit) => [unknown, number] | undefined;

/** Il test decide le risposte che gli interessano; le altre chiamate hanno una risposta
 * fissa: la dispensa vuota, una categoria, la variante per `r2` e l'originale per il resto. */
function stubFetch(route: Rotta = () => undefined) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    const [body, status] = route(path, init) ??
      (path.includes("/pantry")
        ? [[], 200]
        : path.includes("/recipes/categories")
          ? [["Primi piatti"], 200]
          : path.includes("/recipes/r2")
            ? [VARIANTE, 200]
            : [ORIGINALE, 200]);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** L'indirizzo corrente, per i test che devono dire dove si è (e dove non si è andati). */
function Indirizzo() {
  return <output data-testid="indirizzo">{useLocation().pathname}</output>;
}

function renderAt(entry: string | { pathname: string; state: unknown }) {
  const client = createTestQueryClient();
  return render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            <Route path="/ricette" element={<p>Il ricettario</p>} />
            <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
            <Route path="/ricette/:id/variante" element={<RecipeVariantScreen />} />
          </Routes>
          <Indirizzo />
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

/** I corpi mandati con quel metodo a un indirizzo che finisce così. */
function mandati(spy: ReturnType<typeof stubFetch>, metodo: string, fine: string) {
  return spy.mock.calls
    .filter(([url, init]) => (init?.method ?? "GET") === metodo && String(url).endsWith(fine))
    .map(([, init]) => JSON.parse(String(init!.body)));
}

async function apriIlPannello() {
  const azioni = await screen.findByRole("toolbar", { name: "Azioni della ricetta" });
  await userEvent.click(within(azioni).getByRole("button", { name: "Modifica con AI" }));
  return screen.getByLabelText("Cosa vuoi cambiare?");
}

// Frase copiata esatta dalla spec §5 (llm-haiku-design).
const CREDITO =
  "L'AI non risponde: il credito della chiave API è finito. Va ricaricato nella console di Anthropic.";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("«Modifica con AI» nel dettaglio (R8)", () => {
  it("è un'icona fra «Modifica» ed «Elimina», e apre il pannello col fuoco nel campo", async () => {
    stubFetch();
    renderAt("/ricette/r1");

    const azioni = await screen.findByRole("toolbar", { name: "Azioni della ricetta" });
    expect(Array.from(azioni.children).map((el) => el.getAttribute("aria-label"))).toEqual([
      "Modifica", "Modifica con AI", "Elimina",
    ]);
    const tasto = within(azioni).getByRole("button", { name: "Modifica con AI" });
    expect(tasto).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(tasto);

    expect(tasto).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByLabelText("Cosa vuoi cambiare?")).toHaveFocus();
    expect(
      screen.getByText("L'AI scrive una ricetta nuova, che correggi prima di salvare. Questa resta com'è.")
    ).toBeInTheDocument();
  });

  it("con meno di tre lettere «Proponi la variante» dice perché e non parte", async () => {
    const spy = stubFetch();
    renderAt("/ricette/r1");

    await userEvent.type(await apriIlPannello(), "zu");
    const proponi = screen.getByRole("button", { name: "Proponi la variante" });
    expect(proponi).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Scrivi cosa cambiare: bastano tre lettere.")).toBeInTheDocument();
    await userEvent.click(proponi);

    expect(mandati(spy, "POST", "/ai-variant")).toEqual([]);
  });

  it("«Annulla» chiude il pannello e ridà il fuoco a «Modifica con AI»", async () => {
    stubFetch();
    renderAt("/ricette/r1");

    await apriIlPannello();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));

    expect(screen.queryByLabelText("Cosa vuoi cambiare?")).toBeNull();
    const tasto = screen.getByRole("button", { name: "Modifica con AI" });
    expect(tasto).toHaveFocus();
    expect(tasto).toHaveAttribute("aria-expanded", "false");
  });

  it("se l'AI non risponde dice perché", async () => {
    stubFetch((path) =>
      path.endsWith("/ai-variant") ? [{ code: "llm_credit", detail: CREDITO }, 503] : undefined
    );
    renderAt("/ricette/r1");

    const campo = await apriIlPannello();
    await userEvent.type(campo, "senza basilico");
    await userEvent.click(screen.getByRole("button", { name: "Proponi la variante" }));

    const avviso = await screen.findByText(`${CREDITO} Questa ricetta resta com'è.`);
    expect(avviso).toHaveAttribute("role", "alert");
    expect(campo).toHaveValue("senza basilico");
  });

  it("se l'AI non risponde si resta sulla ricetta, col testo scritto e l'avviso ambra", async () => {
    stubFetch((path) =>
      path.endsWith("/ai-variant") ? [{ detail: "variante AI non disponibile" }, 503] : undefined
    );
    renderAt("/ricette/r1");

    const campo = await apriIlPannello();
    await userEvent.type(campo, "senza basilico");
    await userEvent.click(screen.getByRole("button", { name: "Proponi la variante" }));

    const avviso = await screen.findByText(
      "L'AI non ha risposto: questa ricetta resta com'è. Riprova fra poco."
    );
    expect(avviso).toHaveAttribute("role", "alert");
    expect(avviso).toHaveClass("text-low");
    expect(screen.getByRole("heading", { level: 1, name: "Pasta al pomodoro" })).toBeInTheDocument();
    expect(campo).toHaveValue("senza basilico");
    expect(screen.queryByRole("heading", { name: "Nuova variante" })).toBeNull();
  });

  it("una proposta che arriva dopo «Annulla» non apre niente: si resta sull'originale", async () => {
    const spy = stubFetch();
    // la risposta di /ai-variant resta in mano al test: arriva quando decide lui
    const normale = spy.getMockImplementation()!;
    let consegna: (risposta: Response) => void = () => {};
    const inVolo = new Promise<Response>((resolve) => {
      consegna = resolve;
    });
    spy.mockImplementation((url, init) =>
      String(url).endsWith("/ai-variant") ? inVolo : normale(url, init)
    );
    renderAt("/ricette/r1");

    await userEvent.type(await apriIlPannello(), "senza basilico");
    await userEvent.click(screen.getByRole("button", { name: "Proponi la variante" }));
    await vi.waitFor(() => expect(mandati(spy, "POST", "/ai-variant")).toHaveLength(1));
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.queryByLabelText("Cosa vuoi cambiare?")).toBeNull();

    // la proposta arriva a pannello chiuso: il pannello non c'è più, e con lui la sua
    // callback. Si aspetta che la risposta sia stata letta e che i timer di react-query
    // abbiano girato, poi si guarda: nessun modulo, e l'indirizzo è ancora quello dell'originale.
    consegna(new Response(JSON.stringify(PROPOSTA), { status: 200 }));
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(screen.queryByRole("heading", { name: "Nuova variante" })).toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "Pasta al pomodoro" })).toBeInTheDocument();
    expect(screen.getByTestId("indirizzo")).toHaveTextContent(/^\/ricette\/r1$/);
  });

  it("una ricetta eliminata non ha «Modifica con AI»", async () => {
    stubFetch((path) =>
      path.endsWith("/recipes/r1") ? [{ ...ORIGINALE, archived_at: "2026-10-01T10:00:00Z" }, 200] : undefined
    );
    renderAt("/ricette/r1");

    expect(await screen.findByText("Questa ricetta è stata eliminata.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Modifica con AI" })).toBeNull();
  });
});

describe("la variante, dalla proposta al salvataggio (R8)", () => {
  it("la proposta apre il modulo già compilato, e «Salva la variante» crea una ricetta nuova legata all'originale", async () => {
    const spy = stubFetch((path, init) => {
      if (path.endsWith("/ai-variant")) return [PROPOSTA, 200];
      if (path.endsWith("/api/v1/recipes") && init?.method === "POST") return [VARIANTE, 201];
      return undefined;
    });
    renderAt("/ricette/r1");

    await userEvent.type(await apriIlPannello(), "senza basilico");
    await userEvent.click(screen.getByRole("button", { name: "Proponi la variante" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Nuova variante" })).toBeInTheDocument();
    expect(mandati(spy, "POST", "/recipes/r1/ai-variant")).toEqual([{ prompt: "senza basilico" }]);
    expect(screen.getByText("Variante di «Pasta al pomodoro»")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Hai chiesto: «senza basilico». Correggi quel che serve: salvando nasce una ricetta nuova, e l'originale resta com'è."
      )
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Titolo")).toHaveValue("Pasta al pomodoro senza basilico");

    await userEvent.click(screen.getByRole("button", { name: "Salva la variante" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Pasta al pomodoro senza basilico" })
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Variante di «Pasta al pomodoro»" })).toHaveAttribute(
      "href", "/ricette/r1"
    );
    expect(screen.getByText("Salvata.")).toBeInTheDocument();
    const [corpo] = mandati(spy, "POST", "/api/v1/recipes");
    expect(corpo).toMatchObject({
      title: "Pasta al pomodoro senza basilico",
      category: "Primi piatti",
      source: "ai",
      source_ref: "prompt: senza basilico",
      derived_from_id: "r1",
      ingredients: [{ ingredient_id: "i1", role: "primary", quantity_text: "200 g" }],
    });
    // la foto e i tempi li copia il server dall'originale (Mattia, 2026-10-13): il modulo
    // non li ha, e non li manda
    for (const campo of ["image_url", "prep_minutes", "cook_minutes"]) {
      expect(corpo).not.toHaveProperty(campo);
    }
    // l'originale non si tocca: nessuna PUT e nessuna PATCH
    expect(
      spy.mock.calls.filter(([, init]) => init?.method === "PUT" || init?.method === "PATCH")
    ).toEqual([]);
  });

  it("con la proposta nella cronologia il modulo riparte da lì, anche dopo un ricaricamento", async () => {
    stubFetch();
    const state: VariantState = {
      prompt: "senza basilico", draft: PROPOSTA, originTitle: "Pasta al pomodoro",
      originCategory: "Primi piatti",
    };
    renderAt({ pathname: "/ricette/r1/variante", state });

    expect(await screen.findByRole("heading", { level: 1, name: "Nuova variante" })).toBeInTheDocument();
    expect(screen.getByLabelText("Titolo")).toHaveValue("Pasta al pomodoro senza basilico");
    expect(screen.getByRole("button", { name: "Salva la variante" })).toBeInTheDocument();
  });

  it("senza la proposta nella cronologia, «/variante» porta alla ricetta", async () => {
    stubFetch();
    renderAt("/ricette/r1/variante");

    expect(await screen.findByRole("heading", { level: 1, name: "Pasta al pomodoro" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Nuova variante" })).toBeNull();
  });
});

describe("il legame nel dettaglio della variante (R8)", () => {
  it("«Variante di «…»» porta all'originale, che non ne ha uno suo", async () => {
    stubFetch();
    renderAt("/ricette/r2");

    await userEvent.click(await screen.findByRole("link", { name: "Variante di «Pasta al pomodoro»" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Pasta al pomodoro" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Variante di/ })).toBeNull();
  });

  it("un'originale eliminata si legge «(eliminata)», e il legame porta alla sua lapide", async () => {
    stubFetch((path) =>
      path.endsWith("/recipes/r2")
        ? [{ ...VARIANTE, derived_from: { id: "r1", title: "Pasta al pomodoro", archived: true } }, 200]
        : path.endsWith("/recipes/r1")
          ? [{ ...ORIGINALE, archived_at: "2026-10-01T10:00:00Z" }, 200]
          : undefined
    );
    renderAt("/ricette/r2");

    await userEvent.click(
      await screen.findByRole("link", { name: "Variante di «Pasta al pomodoro» (eliminata)" })
    );

    expect(await screen.findByText("Questa ricetta è stata eliminata.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ripristina" })).toBeInTheDocument();
  });

  it("dalla variante all'originale il dettaglio riparte da capo: le porzioni scelte non passano", async () => {
    const spy = stubFetch();
    renderAt("/ricette/r2");

    await userEvent.click(await screen.findByRole("button", { name: "Una porzione in più" }));
    await vi.waitFor(() =>
      expect(spy.mock.calls.some(([url]) => String(url).endsWith("/recipes/r2?servings=3"))).toBe(true)
    );
    await userEvent.click(screen.getByRole("link", { name: "Variante di «Pasta al pomodoro»" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Pasta al pomodoro" })).toBeInTheDocument();
    const letture = spy.mock.calls.map(([url]) => String(url)).filter((url) => url.includes("/recipes/r1"));
    expect(letture).toContain("/api/v1/recipes/r1");
    expect(letture.filter((url) => url.includes("servings"))).toEqual([]);
  });
});
