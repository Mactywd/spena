import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { RecipeDetailScreen } from "./RecipeDetailScreen";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { PantryItem, RecipeDetail } from "../../domain/types";

const DETAIL: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: "Di sempre", source: "manual",
  missing: 2, cookable: false, missing_names: ["Basilico", "Pomodoro"], image_url: null, prep_minutes: null, cook_minutes: null,
  category: null, cost: null, archived_at: null, main_department: null, instructions: "Cuoci.",
  servings: 2, source_ref: null, scaled_to: null, owned_by_import: false,
  // quattro righe su cinque portano una dose: «basilico» non ne ha nessuna, ed è la
  // riga che tiene onesto il denominatore — il conto delle dosi non è il conto degli
  // ingredienti, e il server manda il primo
  unscalable_lines: 0, dose_lines: 4,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "180 g",
      quantity_display: "180 g", quantity_scaled: false,
      note: null, availability: "available", satisfied: true },
    { ingredient_id: "i2", ingredient_name: "pomodoro", role: "primary", quantity_text: "400 g",
      quantity_display: "400 g", quantity_scaled: false,
      note: null, availability: "low", satisfied: false },
    { ingredient_id: "i3", ingredient_name: "aglio", role: "secondary", quantity_text: "q.b.",
      quantity_display: "q.b.", quantity_scaled: false,
      note: null, availability: "low", satisfied: true },
    // senza una riga che manca, metà di statusNote non è coperta da niente
    { ingredient_id: "i4", ingredient_name: "basilico", role: "secondary", quantity_text: null,
      quantity_display: null, quantity_scaled: false,
      note: null, availability: "missing", satisfied: false },
    { ingredient_id: "i5", ingredient_name: "olio", role: "secondary", quantity_text: "q.b.",
      quantity_display: "q.b.", quantity_scaled: false,
      note: null, availability: "available", satisfied: true },
  ],
};

const PANTRY: PantryItem[] = [
  { id: "p1", ingredient_id: "i1", product_id: null, ingredient_name: "pasta",
    ingredient_category: "cereali", product_name: null, product_brand: null,
    status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z", expires_on: null, expiry: null },
  { id: "p2", ingredient_id: "i2", product_id: "pr1", ingredient_name: "pomodoro",
    ingredient_category: "conserve", product_name: "Pelati", product_brand: "Mutti",
    status: "low", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z", expires_on: null, expiry: null },
];

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // senza `NoticeProvider` l'avviso unico (l'esito della cottura, «Metti in lista…»,
  // l'eliminazione) non avrebbe dove comparire
  return render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <MemoryRouter initialEntries={["/ricette/r1"]}>
          <Routes>
            <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

/** Lo stesso dettaglio del file, con una provenienza diversa.
 *
 * `mockImplementation` e non `mockResolvedValue`: la schermata fa più di una
 * chiamata, e il corpo di una Response si legge una volta sola. */
function stubFetchWithSourceRef(sourceRef: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ ...DETAIL, source: "dataset", source_ref: sourceRef }), {
          status: 200,
        })
      )
    )
  );
}

/** Lo stesso dettaglio del file, con delle proprietà sostituite.
 *
 * `mockImplementation` e non `mockResolvedValue`: la schermata fa più di una
 * chiamata, e il corpo di una Response si legge una volta sola. */
function stubFetch(overrides: Partial<typeof DETAIL>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ ...DETAIL, ...overrides }), { status: 200 })
      )
    )
  );
}

describe("RecipeDetailScreen", () => {
  it("distingue ingredienti principali e secondari", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("Principali")).toBeDefined();
    expect(screen.getByText("Secondari")).toBeDefined();
  });

  it("un principale quasi finito ha il pallino giallo e, accanto al nome, «non basta»", async () => {
    // il verdetto arriva dal server (`satisfied`): qui si legge, non si ricalcola
    stubFetch({});
    renderScreen();
    const row = (await screen.findByText("pomodoro")).closest("li")!;
    expect(within(row).getByRole("img", { name: "quasi finito" })).toBeInTheDocument();
    expect(within(row).getByText("non basta")).toBeInTheDocument();
  });

  it("un secondario quasi finito basta: stesso pallino, e nessun «non basta»", async () => {
    stubFetch({});
    renderScreen();
    const row = (await screen.findByText("aglio")).closest("li")!;
    expect(within(row).getByRole("img", { name: "quasi finito" })).toBeInTheDocument();
    expect(within(row).queryByText("non basta")).toBeNull();
  });

  it("l'ordine delle righe è quello del backend: niente qui le riordina", async () => {
    // quantity_text è testo da mostrare: non entra in un ordinamento, in un
    // confronto né in un calcolo. L'ordine è quello che ha deciso il server.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    const principali = (await screen.findByText("Principali")).closest("section")!;
    expect(
      within(principali)
        .getAllByRole("listitem")
        .map((row) => row.textContent)
    ).toEqual(["pasta180 g", "pomodoronon basta400 g"]);
  });

  it("dice cosa manca e cosa c'è, non solo i casi a metà", async () => {
    // Scambiare "manca" e "disponibile" è l'output più fuorviante possibile di
    // questo schermo: l'utente va a fare la spesa per qualcosa che ha, e cucina
    // credendo di avere qualcosa che non ha.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    const assente = (await screen.findByText("basilico")).closest("li")!;
    expect(within(assente).getByRole("img", { name: "manca" })).toBeInTheDocument();

    const presente = screen.getByText("pasta").closest("li")!;
    expect(within(presente).getByRole("img", { name: "disponibile" })).toBeInTheDocument();
  });

  it("una cottura riuscita dice quanto è tornato in lista, col numero del backend", async () => {
    // È l'output del gesto per cui esiste tutto il task: chi dichiara finito un
    // vasetto deve sapere che è tornato in lista. Il numero arriva dal server —
    // qui ne dichiariamo uno solo e il backend ne risponde due, perché contarli
    // da questa parte sarebbe una supposizione.
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown, init?: RequestInit) => {
        if (String(url).includes("/cook")) {
          return Promise.resolve(
            new Response(JSON.stringify({ event_id: "e1", updated: 1, restocked: 2 }), {
              status: 201,
            })
          );
        }
        if (String(url).includes("/pantry")) {
          return Promise.resolve(new Response(JSON.stringify(PANTRY), { status: 200 }));
        }
        expect(init?.method ?? "GET").toBe("GET");
        return Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }));
      })
    );

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: "Cucina" }));
    const row = (await screen.findByText("Pelati")).closest("li")!;
    await userEvent.click(within(row).getByRole("radio", { name: "Finito" }));
    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

    expect(await screen.findByText("Segnato. 2 cose sono tornate in lista della spesa.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Segnato. 2 cose sono tornate in lista della spesa.");
  });

  it("un fallimento nel caricare la ricetta lo dice, non resta a caricare per sempre, e offre ancora «Riprova»", async () => {
    // Confondere "carico" con "fallito" lascerebbe lo schermo bloccato su "Carico…"
    // in eterno: l'utente non saprebbe mai che non arriverà nulla. Un errore che non è
    // un 404 non è «la ricetta non c'è più»: «Riprova» resta, il ricettario no.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));
    renderScreen();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Non sono riuscito a caricare questa ricetta. Riprova."
    );
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Torna al ricettario" })).toBeNull();
  });

  it("una ricetta che non c'è più lo dice, e riporta al ricettario invece di offrire «Riprova»", async () => {
    // un link vecchio, o una ricetta rifatta dall'import: riprovare non potrebbe riuscire
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) =>
        Promise.resolve(
          String(url).includes("/pantry")
            ? new Response("[]", { status: 200 })
            : new Response(JSON.stringify({ detail: "ricetta inesistente" }), { status: 404 })
        )
      )
    );
    renderScreen();
    expect(await screen.findByRole("alert")).toHaveTextContent("Questa ricetta non c'è più.");
    expect(screen.getByRole("link", { name: "Torna al ricettario" })).toHaveAttribute("href", "/ricette");
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
  });

  it("un fallimento nel caricare la dispensa non apre un foglio di cottura vuoto e muto", async () => {
    // "Cucina" apre CookSheet con le voci di dispensa: se la dispensa non si è
    // caricata, offrire comunque il pulsante produrrebbe un foglio che sembra
    // completo ma non lo è, l'errore travestito da "niente da aggiornare".
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) => {
        if (String(url).includes("/pantry")) {
          return Promise.resolve(new Response("", { status: 500 }));
        }
        return Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }));
      })
    );
    renderScreen();
    expect(await screen.findByText("Principali")).toBeDefined();
    expect(await screen.findByRole("alert")).toHaveTextContent(/dispensa/i);
    expect(screen.queryByRole("button", { name: "Cucina" })).toBeNull();
  });

  it("offre l'originale quando la ricetta viene da un indirizzo", async () => {
    stubFetchWithSourceRef("https://ricette.giallozafferano.it/Tiramisu.html");
    renderScreen();

    const link = await screen.findByRole("link", { name: /originale/i });
    expect(link).toHaveAttribute("href", "https://ricette.giallozafferano.it/Tiramisu.html");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
  });

  it("non offre niente quando la provenienza non è un indirizzo", async () => {
    stubFetchWithSourceRef("seme iniziale");
    renderScreen();

    expect(await screen.findByText("Pasta al pomodoro")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /originale/i })).not.toBeInTheDocument();
  });

  it("da una ricetta aperta si torna al ricettario con un tasto", async () => {
    // in una PWA su iOS il tasto indietro del telefono non c'è: senza questo
    // collegamento l'unica uscita è la barra in basso
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    expect((await screen.findByRole("link", { name: "Ricette" })).getAttribute("href"))
      .toBe("/ricette");
  });

  it("la ricetta aperta mostra la sua foto", async () => {
    // fino a ieri si vedeva solo nell'elenco: aprire la ricetta la faceva sparire
    stubFetch({ image_url: "https://esempio.invalid/foto.jpg" });
    renderScreen();
    expect((await screen.findByRole("img", { name: "Pasta al pomodoro" })).getAttribute("src"))
      .toBe("https://esempio.invalid/foto.jpg");
  });

  it("una foto che non carica non lascia un buco sopra il titolo", async () => {
    stubFetch({ image_url: "https://esempio.invalid/rotta.jpg" });
    renderScreen();
    fireEvent.error(await screen.findByRole("img", { name: "Pasta al pomodoro" }));
    expect(screen.queryByRole("img", { name: "Pasta al pomodoro" })).toBeNull();
    // il resto della scheda resta al suo posto
    expect(screen.getByRole("heading", { name: "Pasta al pomodoro" })).toBeDefined();
  });

  /** Come `stubFetch`, ma la risposta dipende dall'indirizzo: qui servono due corpi
   * diversi — la ricetta com'è, e la ricetta riporzionata — e `mockImplementation` è
   * obbligatorio perché il corpo di una Response si legge una volta sola. */
  function stubFetchByUrl(route: (url: string) => unknown) {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) =>
        Promise.resolve(new Response(JSON.stringify(route(String(url))), { status: 200 }))
      )
    );
  }

  // la stessa ricetta chiesta per 2 invece che per 4: è il server a decidere queste
  // stringhe, e il client non le ricalcola — per questo il finto le detta
  const DIMEZZATA = {
    ...DETAIL,
    scaled_to: 2,
    // due «q.b.» che non si riscalano, su quattro righe che una dose ce l'hanno.
    // «basilico» non entra in nessuno dei due numeri: non ha dose, quindi non è una
    // dose mancata — se il denominatore fosse `ingredients.length` si leggerebbe
    // «2 dosi su 5» e si andrebbe a cercare una quinta dose che non esiste
    unscalable_lines: 2,
    dose_lines: 4,
    ingredients: [
      { ...DETAIL.ingredients[0], quantity_display: "90 g", quantity_scaled: true },
      { ...DETAIL.ingredients[1], quantity_display: "200 g", quantity_scaled: true },
      { ...DETAIL.ingredients[2], quantity_display: "q.b.", quantity_scaled: false },
      { ...DETAIL.ingredients[3], quantity_display: null, quantity_scaled: false },
      { ...DETAIL.ingredients[4], quantity_display: "q.b.", quantity_scaled: false },
    ],
  };

  it("il selettore delle porzioni rilegge la ricetta e mostra quel che dice il server", async () => {
    // il client non fa aritmetica: chiede e mostra. È la riga di CLAUDE.md che tiene
    // in piedi la porta a Capacitor.
    const spy = vi.fn();
    stubFetchByUrl((url) => {
      spy(url);
      return url.includes("servings=1") ? DIMEZZATA : DETAIL;
    });

    renderScreen();
    expect(await screen.findByText("180 g")).toBeDefined();

    // DETAIL è per 2 porzioni: un tocco porta a 1
    await userEvent.click(screen.getByRole("button", { name: "Una porzione in meno" }));

    expect(await screen.findByText("90 g")).toBeDefined();
    // e la copertura si dichiara invece di far finta di niente. «su 4» sono le dosi
    // della ricetta, non i suoi cinque ingredienti: il denominatore arriva dal
    // server, che è l'unico a sapere quali righe una dose ce l'hanno. Prima di
    // questa correzione la schermata usava `ingredients.length`, e questa stessa
    // frase era vera per il motivo sbagliato — su una ricetta importata con quattro
    // righe senza dose mandava a cercare quattro dosi inesistenti.
    expect(screen.getByText(/2 dosi su 4 non si riscalano/)).toBeDefined();
    expect(screen.queryByText(/su 5/)).toBeNull();
    expect(spy.mock.calls.some(([url]) => String(url).includes("servings=1"))).toBe(true);
  });

  it("mentre rilegge per porzioni nuove, lo schermo non sparisce da sotto il dito", async () => {
    // `servings` sta nella chiave della query, quindi ogni tocco è una chiave nuova
    // e senza cache: con `isLoading` a comandare il ritorno anticipato, tutta la
    // schermata diventava «Carico…» a metà rilettura e il pulsante spariva mentre lo
    // si premeva — toccare «+» due volte di fila era impossibile. Invisibile in
    // locale, dove la risposta arriva prima del dito.
    let rilascia = () => {};
    const inVolo = new Promise<void>((resolve) => {
      rilascia = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: unknown) => {
        if (String(url).includes("servings=1")) {
          await inVolo;
          return new Response(JSON.stringify(DIMEZZATA), { status: 200 });
        }
        return new Response(JSON.stringify(DETAIL), { status: 200 });
      })
    );

    renderScreen();
    expect(await screen.findByText("180 g")).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: "Una porzione in meno" }));

    // la seconda risposta è ancora per aria: quel che c'era resta
    expect(screen.queryByText("Carico…")).toBeNull();
    expect(screen.getByRole("heading", { name: "Pasta al pomodoro" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Una porzione in meno" })).toBeDefined();
    expect(screen.getByText("180 g")).toBeDefined();

    rilascia();
    expect(await screen.findByText("90 g")).toBeDefined();
  });

  it("a 1× nessuna riga è invariabile: la copertura non compare", async () => {
    // il "solo quando" della regola: la riga di copertura non deve comparire quando
    // non c'è niente da segnalare, ed è proprio quel che vede chiunque apra una
    // ricetta per la prima volta, senza toccare lo stepper
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    await screen.findByText("180 g");
    expect(screen.queryByText(/non si riscala/)).toBeNull();
  });

  it("senza porzioni dichiarate il selettore c'è, e dice perché è fermo", async () => {
    const spy = vi.fn((_url: unknown, _init?: RequestInit) =>
      Promise.resolve(new Response(JSON.stringify({ ...DETAIL, servings: null }), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);
    renderScreen();
    const piu = await screen.findByRole("button", { name: "Una porzione in più" });
    expect(piu).toHaveAttribute("aria-disabled", "true");
    expect(piu).toHaveAccessibleDescription("Porzioni non indicate: si cambiano da «Modifica».");
    await userEvent.click(piu);
    expect(spy.mock.calls.some(([url]) => String(url).includes("servings="))).toBe(false);
  });
});

describe("il costo nel dettaglio si legge e basta (T3 Consegna 5)", () => {
  // Dal giro: i cinque € erano pulsanti che non sembravano pulsanti, e un tocco scorrendo
  // cambiava il costo. Si cambia da «Modifica», dove il modulo di R10 ce l'ha già.
  it("categoria e costo stanno sotto il titolo, e il costo non si tocca", async () => {
    stubFetch({ category: "Primi", cost: 3 });
    renderScreen();
    expect(await screen.findByRole("img", { name: "Costo 3 su 5" })).toBeInTheDocument();
    expect(screen.getByText("Primi")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Costo \d su 5$/ })).toBeNull();
  });

  it("senza costo non si disegna niente, e nessuna PATCH parte", async () => {
    const spy = vi.fn((_url: unknown, _init?: RequestInit) =>
      Promise.resolve(new Response(JSON.stringify({ ...DETAIL, cost: null }), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);
    renderScreen();
    await screen.findByRole("heading", { name: "Pasta al pomodoro" });
    expect(screen.queryByRole("img", { name: /^Costo/ })).toBeNull();
    expect(screen.queryByText("non indicato")).toBeNull();
    expect(spy.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);
  });
});

describe("la testa e le azioni del dettaglio (T3 Consegna 5)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("senza foto, o se la foto non carica, il tasto indietro resta sopra il titolo", async () => {
    stubFetch({ image_url: "https://esempio.invalid/rotta.jpg" });
    renderScreen();
    fireEvent.error(await screen.findByRole("img", { name: "Pasta al pomodoro" }));
    const indietro = screen.getByRole("link", { name: "Ricette" });
    const titolo = screen.getByRole("heading", { name: "Pasta al pomodoro" });
    expect(indietro).toHaveAttribute("href", "/ricette");
    expect(indietro.compareDocumentPosition(titolo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("«Metti in lista ciò che manca» manda solo le righe che il server dice non soddisfatte", async () => {
    // pomodoro è «quasi finito» come l'aglio, ma è principale: il server lo dice non
    // soddisfatto, l'aglio no. Il client legge `satisfied` e non rifà la regola.
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      const path = String(url);
      if (path.endsWith("/shopping-list") && init?.method === "POST")
        return Promise.resolve(new Response(JSON.stringify({ id: "s1", added: true }), { status: 201 }));
      if (path.includes("/pantry"))
        return Promise.resolve(new Response(JSON.stringify(PANTRY), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Metti in lista ciò che manca" }));

    expect(await screen.findByText("2 in lista")).toBeInTheDocument();
    const mandate = spy.mock.calls
      .filter(([, init]) => init?.method === "POST")
      .map(([, init]) => JSON.parse(String(init!.body)));
    expect(mandate).toEqual([
      { raw_text: "pomodoro", ingredient_id: "i2" },
      { raw_text: "basilico", ingredient_id: "i4" },
    ]);
  });

  it("con tutto soddisfatto, «Metti in lista ciò che manca» non c'è", async () => {
    stubFetch({ ingredients: DETAIL.ingredients.map((line) => ({ ...line, satisfied: true })) });
    renderScreen();
    await screen.findByRole("heading", { name: "Pasta al pomodoro" });
    expect(screen.queryByRole("button", { name: "Metti in lista ciò che manca" })).toBeNull();
  });

  it("«Cucina» e «Metti in lista ciò che manca» stanno fra gli ingredienti e il procedimento", async () => {
    // dal giro: «Cucina» in fondo, sotto il procedimento, sembrava dire «inizia a cucinare»
    stubCookServer();
    renderScreen();
    const cucina = await screen.findByRole("button", { name: "Cucina" });
    const metti = screen.getByRole("button", { name: "Metti in lista ciò che manca" });
    const secondari = screen.getByRole("heading", { name: "Secondari" });
    const procedimento = screen.getByRole("heading", { name: "Procedimento" });
    const DOPO = Node.DOCUMENT_POSITION_FOLLOWING;
    expect(secondari.compareDocumentPosition(cucina) & DOPO).toBeTruthy();
    expect(cucina.compareDocumentPosition(metti) & DOPO).toBeTruthy();
    expect(metti.compareDocumentPosition(procedimento) & DOPO).toBeTruthy();
  });

  it("mentre la dispensa carica, «Cucina» dice perché non si apre ancora", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) =>
        String(url).includes("/pantry")
          ? new Promise<Response>(() => {})
          : Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }))
      )
    );
    renderScreen();
    const cucina = await screen.findByRole("button", { name: "Cucina" });
    expect(cucina).toHaveAttribute("aria-disabled", "true");
    expect(cucina).toHaveAccessibleDescription("Carico la dispensa…");
    await userEvent.click(cucina);
    expect(screen.queryByText(/Tocca solo ciò che è cambiato/)).toBeNull();
  });

  it("un gruppo senza righe non ha la sua intestazione", async () => {
    stubFetch({ ingredients: [DETAIL.ingredients[0]] });
    renderScreen();
    expect(await screen.findByRole("heading", { name: "Principali" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Secondari" })).toBeNull();
  });
});

/** Ricetta, dispensa e una cottura che riesce: il giro intero di «Cucina». */
function stubCookServer() {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: unknown) => {
      if (String(url).includes("/cook")) {
        return Promise.resolve(
          new Response(JSON.stringify({ event_id: "e1", updated: 1, restocked: 1 }), {
            status: 201,
          })
        );
      }
      if (String(url).includes("/pantry")) {
        return Promise.resolve(new Response(JSON.stringify(PANTRY), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }));
    })
  );
}

// jsdom non ha layout: non scorre niente e non sa dove stia un elemento. Quel che si
// può controllare qui è *a chi* si chiede di venire in vista e come; che ci arrivi
// davvero sotto l'intestazione fissa lo dice solo un browser vero.
describe("il foglio e l'esito si fanno vedere (T4)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("aprire il foglio porta in vista il suo inizio, non il fondo della pagina", async () => {
    stubCookServer();
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Cucina" }));

    const hint = await screen.findByText(/Tocca solo ciò che è cambiato/);
    await vi.waitFor(() => expect(scroll).toHaveBeenCalled());
    const target = scroll.mock.contexts.at(-1) as HTMLElement;
    // l'elemento che scorre contiene la prima riga del foglio: è l'inizio del foglio
    // che deve arrivare in cima, non un pezzo qualunque
    expect(target).toContainElement(hint);
    expect(scroll).toHaveBeenLastCalledWith({ block: "start", behavior: "smooth" });
  });

  it("chi ha chiesto meno movimento non riceve lo scorrimento animato", async () => {
    stubCookServer();
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query: string) => ({ matches: query === "(prefers-reduced-motion: reduce)" }))
    );
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Cucina" }));

    await vi.waitFor(() => expect(scroll).toHaveBeenCalled());
    expect(scroll).toHaveBeenLastCalledWith({ block: "start", behavior: "auto" });
  });

  it("dopo «Ho cucinato» l'esito passa dall'avviso, e il fuoco torna su «Cucina»", async () => {
    // Il foglio si smonta col pulsante che aveva il fuoco: senza, il fuoco finirebbe sul
    // `body`. L'esito lo dice l'avviso unico (T4, spec T3 §3.5), in un punto fisso, con
    // lo stesso testo di prima.
    stubCookServer();
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Cucina" }));
    const row = (await screen.findByText("Pelati")).closest("li")!;
    await userEvent.click(within(row).getByRole("radio", { name: "Finito" }));
    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

    expect(await screen.findByText("Segnato. Una cosa è tornata in lista della spesa.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Segnato. Una cosa è tornata in lista della spesa.");
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Cucina" })).toHaveFocus());
  });

  it("annullare il foglio non inventa un esito, e riporta il fuoco su «Cucina»", async () => {
    stubCookServer();
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Cucina" }));
    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));

    const cucina = await screen.findByRole("button", { name: "Cucina" });
    await vi.waitFor(() => expect(cucina).toHaveFocus());
    // la regione dell'avviso c'è sempre, vuota finché nessuno parla
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });
});
