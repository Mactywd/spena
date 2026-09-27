import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { IngredientScreen } from "./IngredientScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { Ingredient, IngredientDetail } from "../../domain/types";

const POMODORI: IngredientDetail = {
  id: "i-pomodori", name: "pomodori", display_name: "Pomodori", category: "verdura", kind: "food",
  aliases: [
    { id: "a-pelati", alias: "pomodori pelati", source: "import", decided_in_queue: true },
    { id: "a-pomodorini", alias: "pomodorini", source: "manual", decided_in_queue: false },
  ],
  products: [{ id: "p-cirio", name: "Pelati Cirio", brand: "Cirio", barcode: "8004567890120" }],
  usage: { recipes: 42, pantry: 1, shopping: 1 },
};
const POMODORO: Ingredient = {
  id: "i-pomodoro", name: "pomodoro", display_name: "Pomodoro", category: "verdura", kind: "food",
};

type FetchRoute = (path: string, init?: RequestInit) => [unknown, number];

function stubRoutedFetch(route: FetchRoute) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    // un 204 non ha corpo, e `new Response` rifiuta di costruirne uno che ce l'ha
    return Promise.resolve(
      status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status })
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function callsTo(spy: ReturnType<typeof stubRoutedFetch>, method: string, suffix: string) {
  return spy.mock.calls.filter(
    ([url, init]) =>
      String(url).endsWith(suffix) && ((init as RequestInit | undefined)?.method ?? "GET") === method
  );
}

function Where() {
  const location = useLocation();
  return <p>dove: {location.pathname + location.search}</p>;
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: defaultQueryRetryPredicate } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/anagrafica/ingrediente/:id" element={<IngredientScreen />} />
          <Route path="*" element={<Where />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

/** Le risposte di sempre: la scheda di «pomodori», e la ricerca che trova «pomodoro». */
function base(path: string): [unknown, number] | null {
  if (path.includes("/ingredients/search")) return [[POMODORO], 200];
  if (path.endsWith("/ingredients/i-pomodori")) return [POMODORI, 200];
  return null;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("IngredientScreen", () => {
  it("dice cos'è e dove è usato, prima di ogni correzione", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    expect(await screen.findByRole("heading", { name: "Pomodori" })).toBeInTheDocument();
    expect(screen.getByText("verdura · in 42 ricette · 1 in dispensa · in lista")).toBeInTheDocument();
  });

  it("un alias della coda porta alla coda; uno scritto a mano si sposta e si toglie", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    expect(await screen.findByRole("link", { name: "Deciso nella coda" })).toHaveAttribute(
      "href", "/ricette/importa"
    );
    expect(screen.getByRole("button", { name: "Sposta l'alias «pomodorini»" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Togli l'alias «pomodorini»" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sposta l'alias «pomodori pelati»" })).toBeNull();
  });

  it("«Togli» manda la DELETE dell'alias", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "DELETE") return [null, 204];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Togli l'alias «pomodorini»" }));

    await waitFor(() =>
      expect(callsTo(spy, "DELETE", "/ingredients/i-pomodori/aliases/a-pomodorini")).toHaveLength(1)
    );
  });

  it("«Sposta» chiede l'ingrediente, senza filtro sul tipo, e manda la PATCH", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        return [{ alias: { ...POMODORI.aliases[1] }, ingredient: POMODORO }, 200];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Sposta l'alias «pomodorini»" }));
    await userEvent.type(screen.getByLabelText("Sposta «pomodorini» sotto"), "pomod");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    await waitFor(() =>
      expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori/aliases/a-pomodorini")).toHaveLength(1)
    );
    const [, init] = callsTo(spy, "PATCH", "/ingredients/i-pomodori/aliases/a-pomodorini")[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ ingredient_id: "i-pomodoro" });
    expect(spy.mock.calls.some(([url]) => String(url).includes("kind="))).toBe(false);
  });

  it("un alias della coda rifiutato dice perché, e porta alla coda", async () => {
    stubRoutedFetch((path, init) => {
      if (init?.method === "DELETE") {
        return [{
          code: "import_alias",
          detail: "«pomodorini» viene dalla decisione su «Pomodorini» nella coda: si corregge da lì.",
          term: { id: "t1", display_name: "Pomodorini" },
        }, 409];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Togli l'alias «pomodorini»" }));

    expect(await screen.findByText(/si corregge da lì/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Vai alla coda" })).toHaveAttribute("href", "/ricette/importa");
  });

  it("dalla dispensa: i prodotti portano alla loro scheda e l'origine li segue", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori?da=dispensa");

    expect(await screen.findByRole("link", { name: /Pelati Cirio/ })).toHaveAttribute(
      "href", "/anagrafica/prodotto/p-cirio?da=dispensa"
    );
    expect(screen.getByRole("link", { name: "Dispensa" })).toHaveAttribute("href", "/dispensa");
  });

  it("senza origine si torna all'anagrafica", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    expect(await screen.findByRole("link", { name: /Pelati Cirio/ })).toHaveAttribute(
      "href", "/anagrafica/prodotto/p-cirio"
    );
    expect(screen.getByRole("link", { name: "Anagrafica" })).toHaveAttribute("href", "/anagrafica");
  });

  it(
    "un ingrediente che non c'è più lo dice, invece di un «riprova» che non può riuscire",
    async () => {
      // il 404 si ritenta due volte col predicato vero (Parte X): da qui il tempo lungo
      stubRoutedFetch(() => [{ detail: "ingrediente inesistente" }, 404]);
      renderAt("/anagrafica/ingrediente/i-sparito");

      expect(
        await screen.findByText(/Questo ingrediente non c'è più/, undefined, { timeout: 8000 })
      ).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
    },
    10000
  );
});
