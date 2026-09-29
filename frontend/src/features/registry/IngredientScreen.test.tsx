import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { IngredientScreen } from "./IngredientScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { Ingredient, IngredientDetail, MergeCounts } from "../../domain/types";

const POMODORI: IngredientDetail = {
  id: "i-pomodori", name: "pomodori", display_name: "Pomodori", category: "verdura", kind: "food",
  aliases: [
    { id: "a-pelati", alias: "pomodori pelati", source: "import", decided_in_queue: true, term_id: "t-pelati" },
    { id: "a-pomodorini", alias: "pomodorini", source: "manual", decided_in_queue: false, term_id: null },
  ],
  products: [{ id: "p-cirio", name: "Pelati Cirio", brand: "Cirio", barcode: "8004567890120" }],
  usage: { recipes: 42, pantry: 1, shopping: 1 },
};
const POMODORO: Ingredient = {
  id: "i-pomodoro", name: "pomodoro", display_name: "Pomodoro", category: "verdura", kind: "food",
};
const POMODORO_SCHEDA: IngredientDetail = {
  ...POMODORO, aliases: [], products: [], usage: { recipes: 3, pantry: 1, shopping: 0 },
};
const DETERSIVO: Ingredient = {
  id: "i-detersivo", name: "detersivo", display_name: "Detersivo", category: "casa", kind: "non_food",
};
const ANTEPRIMA: MergeCounts = {
  dry_run: true, loser_name: "pomodori", winner_id: "i-pomodoro", winner_name: "pomodoro",
  recipes_rebuilt: 2, recipe_lines_moved: 1, pantry_items: 1, shopping_items: 0,
  shopping_items_dropped: 0, products: 0,
  aliases: 2, cooking_events_relinked: 0,
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
  const utils = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/anagrafica/ingrediente/:id" element={<IngredientScreen />} />
          <Route path="*" element={<Where />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { client, ...utils };
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

    // dritto al termine della decisione, non in cima alla coda a cercarlo
    expect(await screen.findByRole("link", { name: "Deciso nella coda" })).toHaveAttribute(
      "href", "/ricette/importa?termine=t-pelati"
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

  it("uno spostamento che fa sparire l'alias (il testo esisteva già) lo dice, invece di sparire muto", async () => {
    // AliasMovedOut.alias: null (backend/app/services/registry.py, move_alias): il
    // testo esisteva già come nome o alias — sul bersaglio o su un terzo ingrediente —
    // e `remember_alias` lo scarta invece di raddoppiarlo. Silenziosamente la riga
    // spariva e basta: l'utente non aveva modo di sapere se lo spostamento fosse
    // andato a segno o no
    let mosso = false;
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH" && path.includes("/aliases/")) {
        mosso = true;
        return [{ alias: null, ingredient: POMODORO }, 200];
      }
      if (path.includes("/ingredients/search")) return [[POMODORO], 200];
      if (path.endsWith("/ingredients/i-pomodori")) {
        return [
          mosso
            ? { ...POMODORI, aliases: POMODORI.aliases.filter((a) => a.alias !== "pomodorini") }
            : POMODORI,
          200,
        ];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Sposta l'alias «pomodorini»" }));
    await userEvent.type(screen.getByLabelText("Sposta «pomodorini» sotto"), "pomod");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    const nota = await screen.findByText(/«pomodorini».*esisteva già.*non si è spostato/);
    // la riga dell'alias sparisce (il server non lo manda più) ma la nota resta:
    // altrimenti sarebbe la stessa sparizione muta, solo ritardata di un giro
    await waitFor(() => expect(screen.queryByRole("button", { name: "Togli l'alias «pomodorini»" })).toBeNull());
    expect(nota).toBeInTheDocument();
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
    const queueLink = screen.getByRole("link", { name: "Vai alla coda" });
    expect(queueLink).toHaveAttribute("href", "/ricette/importa?termine=t1");
    // bersaglio da 44px (regola di casa): non deve regredire in silenzio
    expect(queueLink).toHaveClass("min-h-11");
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
      // il predicato vero (Parte X) non ritenta più un 404 dal 2026-09-29: il tempo
      // lungo resta per l'attesa iniziale della schermata, non per dei ritentativi
      stubRoutedFetch(() => [{ detail: "ingrediente inesistente" }, 404]);
      renderAt("/anagrafica/ingrediente/i-sparito");

      expect(
        await screen.findByText(/Questo ingrediente non c'è più/, undefined, { timeout: 8000 })
      ).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
    },
    10000
  );

  it("«Cambia reparto» manda il reparto scelto, e si richiude", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ ...POMODORI, category: "legumi" }, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia reparto" }));
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "legumi");
    await userEvent.click(screen.getByRole("button", { name: "Salva il reparto" }));

    await waitFor(() => expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(1));
    const [, init] = callsTo(spy, "PATCH", "/ingredients/i-pomodori")[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ category: "legumi" });
    await waitFor(() => expect(screen.queryByLabelText("Reparto")).toBeNull());
  });

  it("il rifiuto per le ricette le elenca, ciascuna col suo link", async () => {
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        return [{
          code: "non_food_in_recipes",
          detail:
            "«Pomodori» è in 42 ricette: non può diventare non alimentare finché una ricetta lo usa.",
          recipe_count: 42,
          recipes: [{ id: "r1", title: "Sugo semplice" }],
          pending_import_count: 0,
          pending_terms: [],
          pending_term_count: 0,
        }, 409];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia reparto" }));
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "casa");
    await userEvent.click(screen.getByRole("button", { name: "Salva il reparto" }));

    expect(await screen.findByText(/non può diventare non alimentare/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sugo semplice" })).toHaveAttribute("href", "/ricette/r1");
    expect(screen.getByText("e altre 41.")).toBeInTheDocument();
    // il reparto scelto resta scelto: si corregge, non si riscrive da capo
    expect(screen.getByLabelText("Reparto")).toHaveValue("casa");
  });

  it("una ricetta eliminata nel rifiuto è segnata, e il suo link porta a «Ripristina»", async () => {
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        return [{
          code: "non_food_in_recipes",
          detail:
            "«Pomodori» è in 1 ricetta: non può diventare non alimentare finché una ricetta lo usa.",
          recipe_count: 1,
          recipes: [{ id: "r1", title: "Sugo semplice", archived: true }],
          pending_import_count: 0,
          pending_terms: [],
          pending_term_count: 0,
        }, 409];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia reparto" }));
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "casa");
    await userEvent.click(screen.getByRole("button", { name: "Salva il reparto" }));

    // il link resta il titolo e basta: la segnatura gli sta accanto
    expect(await screen.findByRole("link", { name: "Sugo semplice" })).toHaveAttribute(
      "href", "/ricette/r1"
    );
    expect(screen.getByText("(eliminata)")).toBeInTheDocument();
  });

  it("il rifiuto per le ricette dell'import in attesa porta alla coda, dove la decisione si annulla", async () => {
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        return [{
          code: "non_food_in_recipes",
          detail:
            "«Pomodori» è in 3 ricette dell'import ancora in attesa: non può diventare non " +
            "alimentare finché una ricetta lo usa.",
          recipe_count: 0,
          recipes: [],
          pending_import_count: 3,
          pending_terms: [
            { id: "t-pelati", display_name: "Pomodori pelati" },
            { id: "t-passata", display_name: "Passata" },
          ],
          pending_term_count: 12,
        }, 409];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia reparto" }));
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "casa");
    await userEvent.click(screen.getByRole("button", { name: "Salva il reparto" }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/3 ricette dell'import ancora in attesa/)).toBeInTheDocument();
    // nessuna ricetta da elencare, quindi nessun elenco vuoto: il solo elenco è dei termini
    expect(within(alert).getAllByRole("list")).toHaveLength(1);
    // un link per termine, dritto al termine in coda: anche quelli decisi da sé, che
    // non hanno alias sulla scheda e non stanno fra le decisioni recenti
    expect(within(alert).getByRole("link", { name: "Pomodori pelati" })).toHaveAttribute(
      "href", "/ricette/importa?termine=t-pelati"
    );
    expect(within(alert).getByText("e altri 10.")).toBeInTheDocument();
    await userEvent.click(within(alert).getByRole("link", { name: "Passata" }));
    expect(await screen.findByText("dove: /ricette/importa?termine=t-passata")).toBeInTheDocument();
  });

  it("l'anteprima dice cosa si sposta, e «Unisci» porta al vincitore con l'esito in vista", async () => {
    // dopo la fusione vera il perdente non c'è più: lo stub lo riflette invece di
    // dichiararlo soltanto (Minor d)
    let fuso = false;
    const spy = stubRoutedFetch((path, init) => {
      if (path.endsWith("/ingredients/i-pomodori/merge")) {
        const { dry_run } = JSON.parse(String(init?.body));
        if (!dry_run) fuso = true;
        return [{ ...ANTEPRIMA, dry_run }, 200];
      }
      if (path.endsWith("/ingredients/i-pomodoro")) return [POMODORO_SCHEDA, 200];
      if (path.endsWith("/ingredients/i-pomodori")) {
        return fuso ? [{ detail: "non c'è più" }, 404] : (base(path) ?? [{}, 404]);
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "pomod");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(
      await screen.findByText(
        "Si spostano 3 ricette, 1 elemento di dispensa, 2 alias. «pomodori» diventa un alias di «pomodoro». Non si annulla."
      )
    ).toBeInTheDocument();
    const getPrimaDellaFusione = callsTo(spy, "GET", "/ingredients/i-pomodori").length;
    await userEvent.click(screen.getByRole("button", { name: "Unisci" }));

    expect(await screen.findByRole("heading", { name: "Pomodoro" })).toBeInTheDocument();
    expect(screen.getByText(/Uniti: «pomodori» ora è un alias di «pomodoro»\./)).toBeInTheDocument();
    const corpi = callsTo(spy, "POST", "/ingredients/i-pomodori/merge").map(([, init]) =>
      JSON.parse(String((init as RequestInit).body))
    );
    expect(corpi).toEqual([
      { into: "i-pomodoro", dry_run: true },
      { into: "i-pomodoro", dry_run: false },
    ]);
    // il successo rilegge senza `refetch` (Task 17): nessuna GET del perdente dopo
    // essere arrivati sulla scheda del vincitore
    expect(callsTo(spy, "GET", "/ingredients/i-pomodori")).toHaveLength(getPrimaDellaFusione);
  });

  it("l'anteprima non si ritenta da sola: «Riprova» compare al primo guasto, e la rilancia", async () => {
    // ogni tentativo è una fusione intera (fino a ~130s, 300s a nginx): il predicato
    // di retry vero ne farebbe fino a tre in coda prima di mostrare «Riprova» — qui
    // se ne conta uno solo (Important 1)
    let tentativi = 0;
    const spy = stubRoutedFetch((path) => {
      if (path.endsWith("/ingredients/i-pomodori/merge")) {
        tentativi += 1;
        return tentativi === 1 ? [{ detail: "errore del server" }, 500] : [ANTEPRIMA, 200];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "pomod");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(await screen.findByText("Non sono riuscito a calcolare l'anteprima.")).toBeInTheDocument();
    expect(callsTo(spy, "POST", "/ingredients/i-pomodori/merge")).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));

    expect(await screen.findByText(/Si spostano/)).toBeInTheDocument();
    expect(callsTo(spy, "POST", "/ingredients/i-pomodori/merge")).toHaveLength(2);
  });

  it(
    "un guasto sulla fusione vera non finge di sapere: rilegge, e se il perdente non c'è " +
      "più passa alla sua schermata",
    async () => {
      // il 500 sulla fusione vera è un guasto di rete/nginx (spec: un 504 misurato),
      // non un rifiuto: il server può averla comunque portata a termine (Important 2)
      let tentata = false;
      const spy = stubRoutedFetch((path, init) => {
        if (path.endsWith("/ingredients/i-pomodori/merge")) {
          const { dry_run } = JSON.parse(String(init?.body));
          if (dry_run) return [{ ...ANTEPRIMA, dry_run }, 200];
          tentata = true;
          return [{ detail: "errore del server" }, 500];
        }
        if (path.endsWith("/ingredients/i-pomodori")) {
          // rileggendo dopo il guasto si scopre che la fusione era andata a segno
          return tentata ? [{ detail: "non c'è più" }, 404] : (base(path) ?? [{}, 404]);
        }
        return base(path) ?? [{}, 404];
      });
      renderAt("/anagrafica/ingrediente/i-pomodori");

      await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
      await userEvent.type(screen.getByLabelText("Unisci a"), "pomod");
      await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
      await screen.findByText(/Si spostano/);

      await userEvent.click(screen.getByRole("button", { name: "Unisci" }));

      // la scheda del perdente, con la rilettura dopo la fusione (il predicato di retry
      // vero, qui, è quello dell'ingrediente — Parte X, che dal 2026-09-29 non ritenta
      // più un 404), scopre subito di essere sparita
      expect(
        await screen.findByText(/Questo ingrediente non c'è più/, undefined, { timeout: 8000 })
      ).toBeInTheDocument();
      expect(screen.queryByText(/Niente è cambiato/)).toBeNull();
      // il guasto è sulla fusione vera, non sull'anteprima: rileggere dopo il guasto
      // non deve rilanciarla in silenzio, un'altra fusione intera da ~130s (fix round 2)
      const anteprime = callsTo(spy, "POST", "/ingredients/i-pomodori/merge").filter(
        ([, init]) => JSON.parse(String((init as RequestInit).body)).dry_run === true
      );
      expect(anteprime).toHaveLength(1);
    },
    10000
  );

  it("«Unisci», «Cambia» e «Lascia com'è» restano spenti, col fuoco, mentre la fusione vera è in corso", async () => {
    let risolviFusione: ((response: Response) => void) | null = null;
    const fusionePendente = new Promise<Response>((resolve) => {
      risolviFusione = resolve;
    });
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      const path = String(url);
      if (path.endsWith("/ingredients/i-pomodori/merge")) {
        const { dry_run } = JSON.parse(String(init?.body));
        if (dry_run) {
          return Promise.resolve(new Response(JSON.stringify({ ...ANTEPRIMA, dry_run }), { status: 200 }));
        }
        return fusionePendente;
      }
      if (path.endsWith("/ingredients/i-pomodoro")) {
        return Promise.resolve(new Response(JSON.stringify(POMODORO_SCHEDA), { status: 200 }));
      }
      const [body, status] = base(path) ?? [{}, 404];
      return Promise.resolve(new Response(JSON.stringify(body), { status }));
    });
    vi.stubGlobal("fetch", spy);

    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "pomod");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await screen.findByText(/Si spostano/);

    await userEvent.click(screen.getByRole("button", { name: "Unisci" }));

    // `busy` e non `disabled` (Consegna 6a): spenti con `aria-disabled`, così chi ha
    // premuto «Unisci» da tastiera tiene il fuoco; e un tocco non fa niente
    const unisco = await screen.findByRole("button", { name: "Unisco…" });
    const cambia = screen.getByRole("button", { name: "Cambia" });
    const lascia = screen.getByRole("button", { name: "Lascia com'è" });
    for (const button of [unisco, cambia, lascia]) {
      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(button.hasAttribute("disabled")).toBe(false);
    }
    await userEvent.click(unisco);
    await userEvent.click(cambia);
    await userEvent.click(lascia);
    // nessuna seconda fusione, il vincitore resta scelto, il pannello resta aperto
    expect(
      spy.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/ingredients/i-pomodori/merge") &&
          JSON.parse(String(init?.body)).dry_run === false
      )
    ).toHaveLength(1);
    expect(screen.getByText(/Resta:/)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Unisci «Pomodori» a un altro ingrediente" })
    ).toBeInTheDocument();

    risolviFusione!(new Response(JSON.stringify({ ...ANTEPRIMA, dry_run: false }), { status: 200 }));

    expect(await screen.findByRole("heading", { name: "Pomodoro" })).toBeInTheDocument();
  });

  it("«Unisci» resta spento mentre l'anteprima si ricalcola dopo un'invalidazione", async () => {
    // `staleTime: Infinity` non blocca un'invalidazione esplicita (F13, docstring di
    // MergePanel): uno spostamento d'alias altrove la rilancia mentre il pannello è
    // aperto, e i vecchi numeri non devono restare confermabili nel frattempo
    let rilanci = 0;
    let risolviSeconda: ((response: Response) => void) | null = null;
    const secondaPendente = new Promise<Response>((resolve) => {
      risolviSeconda = resolve;
    });
    const spy = vi.fn((url: unknown) => {
      const path = String(url);
      if (path.endsWith("/ingredients/i-pomodori/merge")) {
        rilanci += 1;
        if (rilanci === 1) {
          return Promise.resolve(new Response(JSON.stringify({ ...ANTEPRIMA, dry_run: true }), { status: 200 }));
        }
        return secondaPendente;
      }
      const [body, status] = base(path) ?? [{}, 404];
      return Promise.resolve(new Response(JSON.stringify(body), { status }));
    });
    vi.stubGlobal("fetch", spy);

    const { client } = renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "pomod");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await screen.findByText(/Si spostano/);
    expect(screen.getByRole("button", { name: "Unisci" })).not.toHaveAttribute("aria-disabled");

    // una correzione altrove (uno spostamento d'alias, per dire) invalida ["registry"]
    void client.invalidateQueries({ queryKey: ["registry"] });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Unisci" })).toHaveAttribute("aria-disabled", "true")
    );
    // spento, un tocco non conferma i numeri vecchi: nessuna fusione vera parte (le due
    // chiamate sono l'anteprima e il suo ricalcolo)
    await userEvent.click(screen.getByRole("button", { name: "Unisci" }));
    expect(rilanci).toBe(2);
    // i vecchi numeri restano a video (nessun lampo di "Calcolo cosa si sposta…"),
    // ma non si devono poter confermare finché l'anteprima nuova non è arrivata
    expect(screen.getByText(/Si spostano/)).toBeInTheDocument();

    risolviSeconda!(new Response(JSON.stringify({ ...ANTEPRIMA, dry_run: true }), { status: 200 }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Unisci" })).not.toHaveAttribute("aria-disabled")
    );
  });

  it("tra un alimento e una voce non alimentare offre il cambio di reparto", async () => {
    stubRoutedFetch((path) => {
      if (path.endsWith("/ingredients/i-pomodori/merge")) {
        return [{
          code: "kind_mismatch",
          detail:
            "«Pomodori» e «Detersivo» stanno in due metà diverse dell'anagrafica: un alimento e una voce non alimentare non si uniscono. Prima porta «Pomodori» nello stesso reparto di «Detersivo», poi uniscili.",
          existing: DETERSIVO,
        }, 409];
      }
      if (path.includes("/ingredients/search")) return [[DETERSIVO], 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "deter");
    await userEvent.click(await screen.findByRole("option", { name: /Detersivo/ }));

    const avviso = await screen.findByRole("alert");
    expect(avviso).toHaveTextContent("poi uniscili");
    await userEvent.click(within(avviso).getByRole("button", { name: "Cambia reparto" }));
    expect(screen.getByLabelText("Reparto")).toBeInTheDocument();
  });

  it("il rifiuto decision_refused porta al termine nella coda, dove si annulla", async () => {
    stubRoutedFetch((path) => {
      if (path.endsWith("/ingredients/i-pomodori/merge")) {
        return [{
          code: "decision_refused",
          detail:
            "Il termine «Pomodori pelati» dell'import non può finire su «Detersivo», che non è " +
            "un alimento: annullalo o ignoralo in «Ingredienti da abbinare», poi riprova.",
          term: { id: "t-pelati", display_name: "Pomodori pelati" },
        }, 409];
      }
      if (path.includes("/ingredients/search")) return [[DETERSIVO], 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "deter");
    await userEvent.click(await screen.findByRole("option", { name: /Detersivo/ }));

    const avviso = await screen.findByRole("alert");
    expect(avviso).toHaveTextContent("annullalo o ignoralo");
    const link = within(avviso).getByRole("link", { name: "Vai a «Pomodori pelati» nella coda" });
    expect(link).toHaveAttribute("href", "/ricette/importa?termine=t-pelati");
    expect(link).toHaveClass("min-h-11");
  });

  it("il rifiuto kind_mismatch offre anche il link alla scheda del vincitore", async () => {
    // «Cambia reparto» sposta il PERDENTE (questa scheda); l'altra strada — cambiare
    // il reparto del VINCITORE — non aveva modo di arrivarci da qui
    stubRoutedFetch((path) => {
      if (path.endsWith("/ingredients/i-pomodori/merge")) {
        return [{
          code: "kind_mismatch",
          detail: "«Pomodori» e «Detersivo» stanno in due metà diverse dell'anagrafica.",
          existing: DETERSIVO,
        }, 409];
      }
      if (path.includes("/ingredients/search")) return [[DETERSIVO], 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "deter");
    await userEvent.click(await screen.findByRole("option", { name: /Detersivo/ }));

    const avviso = await screen.findByRole("alert");
    expect(within(avviso).getByRole("link", { name: /Detersivo/ })).toHaveAttribute(
      "href", "/anagrafica/ingrediente/i-detersivo"
    );
  });

  it("il link al vincitore del kind_mismatch porta con sé l'origine «dispensa»", async () => {
    stubRoutedFetch((path) => {
      if (path.endsWith("/ingredients/i-pomodori/merge")) {
        return [{
          code: "kind_mismatch",
          detail: "«Pomodori» e «Detersivo» stanno in due metà diverse dell'anagrafica.",
          existing: DETERSIVO,
        }, 409];
      }
      if (path.includes("/ingredients/search")) return [[DETERSIVO], 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori?da=dispensa");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "deter");
    await userEvent.click(await screen.findByRole("option", { name: /Detersivo/ }));

    const avviso = await screen.findByRole("alert");
    expect(within(avviso).getByRole("link", { name: /Detersivo/ })).toHaveAttribute(
      "href", "/anagrafica/ingrediente/i-detersivo?da=dispensa"
    );
  });

  it("avvisa dei tempi lunghi sopra 1.000 ricette, prima ancora che l'anteprima risponda", async () => {
    stubRoutedFetch((path) => {
      if (path.endsWith("/ingredients/i-pomodori")) {
        return [{ ...POMODORI, usage: { recipes: 1001, pantry: 1, shopping: 1 } }, 200];
      }
      if (path.endsWith("/ingredients/i-pomodori/merge")) return [ANTEPRIMA, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "pomod");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(await screen.findByText(/Può volerci qualche minuto/)).toBeInTheDocument();
  });

  it("sotto la soglia delle 1.000 ricette non avvisa dei tempi lunghi", async () => {
    stubRoutedFetch((path) => {
      if (path.endsWith("/ingredients/i-pomodori/merge")) return [ANTEPRIMA, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "pomod");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    await screen.findByText(/Si spostano/);
    expect(screen.queryByText(/Può volerci qualche minuto/)).toBeNull();
  });

  it("«Rinomina» manda il nome nuovo e si richiude", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        return [{ ...POMODORI, name: "pomodori rossi", display_name: "Pomodori rossi" }, 200];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Rinomina" }));
    const campo = screen.getByLabelText("Nuovo nome");
    await userEvent.clear(campo);
    await userEvent.type(campo, "Pomodori rossi");
    await userEvent.click(screen.getByRole("button", { name: "Salva il nome" }));

    await waitFor(() => expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(1));
    const [, init] = callsTo(spy, "PATCH", "/ingredients/i-pomodori")[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ name: "Pomodori rossi" });
    await waitFor(() => expect(screen.queryByLabelText("Nuovo nome")).toBeNull());
  });

  it("un nome già preso offre «Uniscili», e porta alla fusione con quel vincitore già scelto", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        return [{
          code: "name_taken",
          detail: "«pomodoro» è già in anagrafica: uniscili invece di rinominare.",
          existing: POMODORO,
        }, 409];
      }
      if (path.endsWith("/ingredients/i-pomodori/merge")) return [ANTEPRIMA, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Rinomina" }));
    const campo = screen.getByLabelText("Nuovo nome");
    await userEvent.clear(campo);
    await userEvent.type(campo, "Pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Salva il nome" }));

    expect(await screen.findByText("C'è già «Pomodoro». Uniscili?")).toBeInTheDocument();
    // il nome scritto resta nel campo: si corregge, non si riscrive (spec §7)
    expect(screen.getByLabelText("Nuovo nome")).toHaveValue("Pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Uniscili" }));

    expect(await screen.findByText(/«pomodori» diventa un alias di «pomodoro»/)).toBeInTheDocument();
    const [, init] = callsTo(spy, "POST", "/ingredients/i-pomodori/merge")[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      into: "i-pomodoro", dry_run: true,
    });
  });

  it("le correzioni sono un gruppo di icone accanto al titolo, coi nomi di sempre", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    const toolbar = await screen.findByRole("toolbar", { name: "Correzioni dell'ingrediente" });
    // accanto al titolo: nella riga dell'intestazione (`action` di Screen)
    expect(toolbar.parentElement).toContainElement(
      screen.getByRole("heading", { level: 1, name: "Pomodori" })
    );
    const buttons = within(toolbar).getAllByRole("button");
    expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual([
      "Rinomina",
      "Cambia reparto",
      "Unisci a un altro…",
    ]);
    for (const button of buttons) {
      // più pulsanti in gruppo → solo icone (spec T3 §2), col nome di prima come `aria-label`
      expect(button.textContent).toBe("");
      expect(button.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
    }
    await userEvent.click(buttons[0]);
    expect(screen.getByLabelText("Nuovo nome")).toBeInTheDocument();
  });

  it("«Salva il nome» dice perché non salva ancora: il nome è quello di ora, o non c'è", async () => {
    const spy = stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Rinomina" }));
    const salva = screen.getByRole("button", { name: "Salva il nome" });
    // `unavailableReason` (Consegna 6a): spento senza `disabled`, col perché
    expect(salva).toHaveAttribute("aria-disabled", "true");
    expect(salva.hasAttribute("disabled")).toBe(false);
    expect(salva).toHaveAccessibleDescription("È già il suo nome: scrivine un altro.");
    await userEvent.clear(screen.getByLabelText("Nuovo nome"));
    expect(salva).toHaveAccessibleDescription("Scrivi un nome per salvarlo.");
    await userEvent.click(salva);
    expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(0);
  });

  it("«Salva il reparto» a reparto invariato dice perché, e non manda niente", async () => {
    const spy = stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia reparto" }));
    const salva = screen.getByRole("button", { name: "Salva il reparto" });
    expect(salva).toHaveAttribute("aria-disabled", "true");
    expect(salva.hasAttribute("disabled")).toBe(false);
    expect(salva).toHaveAccessibleDescription("È già il suo reparto: scegline un altro.");
    await userEvent.click(salva);
    expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(0);

    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "legumi");
    expect(salva).not.toHaveAttribute("aria-disabled");
    expect(screen.queryByText("È già il suo reparto: scegline un altro.")).toBeNull();
  });

  it("mentre l'alias si toglie, «Sposta» e «Togli» restano spenti col fuoco, e non ripartono", async () => {
    let risolvi: ((response: Response) => void) | null = null;
    const pendente = new Promise<Response>((resolve) => {
      risolvi = resolve;
    });
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      if (init?.method === "DELETE") return pendente;
      const [body, status] = base(String(url)) ?? [{}, 404];
      return Promise.resolve(new Response(JSON.stringify(body), { status }));
    });
    vi.stubGlobal("fetch", spy);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    const togli = await screen.findByRole("button", { name: "Togli l'alias «pomodorini»" });
    const sposta = screen.getByRole("button", { name: "Sposta l'alias «pomodorini»" });
    // `accessibleName` (Consegna 6a): il testo in vista è l'inizio del nome
    expect(togli.textContent).toBe("Togli");
    expect(sposta.textContent).toBe("Sposta");
    await userEvent.click(togli);
    await waitFor(() => expect(togli).toHaveAttribute("aria-disabled", "true"));
    for (const button of [togli, sposta]) {
      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(button.hasAttribute("disabled")).toBe(false);
    }
    expect(togli).toHaveFocus();
    await userEvent.click(togli);
    await userEvent.click(sposta);
    expect(spy.mock.calls.filter(([, init]) => init?.method === "DELETE")).toHaveLength(1);
    // «Sposta» spento non apre la scelta
    expect(screen.queryByLabelText("Sposta «pomodorini» sotto")).toBeNull();

    risolvi!(new Response(null, { status: 204 }));
  });
});
