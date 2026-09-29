import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RecipeBookScreen } from "./RecipeBookScreen";
import { UnauthorizedError } from "../../api/client";

// `kind` c'è perché c'è nella risposta vera, e perché i filtri ricordati scartano un
// ingrediente che non ce l'ha: senza, il test del ricordo mentirebbe
const POMODORO = { id: "i9", name: "pomodoro", display_name: "Pomodoro", category: "verdura", kind: "food" };
const BASILICO = { id: "i7", name: "basilico", display_name: "Basilico", category: "verdura", kind: "food" };

/** L'ultima richiesta di ricerca partita davvero: il filtro cambia la query, e
 * guardare la prima chiamata vorrebbe dire guardare lo schermo prima del gesto. */
function ultimaRicerca(fetchMock: { mock: { calls: unknown[][] } }): string {
  return fetchMock.mock.calls
    .map(([url]) => String(url))
    .filter((u) => u.includes("/recipes/search?"))
    .pop()!;
}

const RESULTS = [
  { id: "r1", title: "Pasta all'aglio", description: "Svelta", source: "dataset",
    missing: 0, cookable: true, missing_names: [], image_url: "https://example.com/aglio.jpg",
    prep_minutes: 10, cook_minutes: 15, category: "Primi piatti", cost: null,
    archived_at: null, main_department: "cereali" },
  { id: "r2", title: "Pasta al pomodoro", description: "Di sempre", source: "ai",
    missing: 1, cookable: false, missing_names: ["Pomodoro"], image_url: null,
    prep_minutes: null, cook_minutes: null, category: null, cost: null,
    archived_at: null, main_department: null },
];

/** Una riga di ricettario coi campi che la risposta vera porta tutti. */
function riga(id: string, title: string, extra: Record<string, unknown> = {}) {
  return { ...RESULTS[1], id, title, missing: 0, cookable: true, missing_names: [], ...extra };
}

function renderScreen(queryCache?: QueryCache) {
  const client = new QueryClient({
    queryCache,
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RecipeBookScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// Nessun ingrediente in attesa: la scheda d'ingresso alla coda non c'è (T3 Consegna 4),
// e la coda resta raggiungibile dal ☰
const NESSUN_IMPORT_IN_CORSO = {
  fetched: 0, pending_recipes: 0, imported: 0, skipped: 0, pending_terms: 0,
};

/** Quel che il finto server risponde a un percorso: il corpo, lo stato e, se servono,
 * le intestazioni (il totale del ricettario sta in `X-Total-Count`). */
type Risposta = [unknown, number, Record<string, string>?];

/** Un fetch che risponde in base al percorso: lo schermo fa tre chiamate — la
 * ricerca, il modo di ricerca e lo stato dell'import — e ognuna deve ricevere una
 * Response nuova, perché il corpo di una Response si legge una volta sola. */
function stubRoutedFetch(route: (path: string) => Risposta) {
  const spy = vi.fn((url: unknown) => {
    const path = String(url);
    const [body, status, headers]: Risposta = path.includes("/imports/status")
      ? [NESSUN_IMPORT_IN_CORSO, 200]
      : route(path);
    return Promise.resolve(new Response(JSON.stringify(body), { status, headers }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** Apre il pannello «Filtri»: categoria e ingredienti stanno lì dentro. */
async function apriFiltri() {
  await userEvent.click(await screen.findByRole("button", { name: /^Filtri/ }));
}

// i filtri si ricordano in sessionStorage: ogni test parte e finisce senza
beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const CODA_CON_CATEGORIE = (path: string): Risposta => {
  if (path.includes("/recipes/categories")) return [["Primi piatti", "Dolci e Desserts"], 200];
  if (path.includes("/recipes/search-mode")) return [{ semantic: true }, 200];
  return [RESULTS, 200];
};

/** Come `CODA_CON_CATEGORIE`, e in più i suggerimenti degli ingredienti. */
const CON_POMODORO = (path: string): Risposta =>
  path.includes("/ingredients") ? [[POMODORO], 200] : CODA_CON_CATEGORIE(path);

describe("RecipeBookScreen", () => {
  it("la riga non dice la provenienza né la descrizione", async () => {
    // dal giro: «dataset» non dice niente a chi usa l'app, e la descrizione la dice il
    // dettaglio (T3 Consegna 4)
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    await screen.findByText("Pasta all'aglio");
    expect(screen.queryByText("dataset")).toBeNull();
    expect(screen.queryByText("AI")).toBeNull();
    expect(screen.queryByText("Svelta")).toBeNull();
  });

  it("dice cosa manca, senza nascondere la ricetta", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    expect(await screen.findByText("Pasta al pomodoro")).toBeDefined();
    expect(screen.getByText("Manca: Pomodoro")).toBeDefined();
  });

  it("segnala le ricette che puoi cucinare adesso", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    expect(await screen.findByText("Hai tutto")).toBeDefined();
  });

  it("la ricerca passa la query al backend", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);

    renderScreen();
    await userEvent.type(await screen.findByLabelText("Cerca nel ricettario"), "pomodoro");

    await vi.waitFor(() =>
      expect(spy.mock.calls.some(([url]) => String(url).includes("q=pomodoro"))).toBe(true)
    );
  });

  it("la scala manda la soglia, e «Ora» manda zero", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    await screen.findByText("Pasta all'aglio");

    await userEvent.click(
      screen.getByRole("radio", { name: "Solo quelle che puoi cucinare adesso." })
    );

    // `max_missing=0`, non l'assenza del parametro: «cucinabili ora» è la soglia più
    // stretta, e un `if (maxMissing)` la scambierebbe per «Tutte» mostrando tutto
    await waitFor(() => expect(ultimaRicerca(spy)).toContain("max_missing=0"));
    expect(ultimaRicerca(spy)).not.toContain("only_cookable");
  });

  it("un gradino più largo manda la sua soglia", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    await screen.findByText("Pasta all'aglio");

    await userEvent.click(
      screen.getByRole("radio", { name: "Al massimo 2 ingredienti da comprare." })
    );

    await waitFor(() => expect(ultimaRicerca(spy)).toContain("max_missing=2"));
  });

  it("senza soglia non manda il parametro", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    await screen.findByText("Pasta all'aglio");

    expect(ultimaRicerca(spy)).not.toContain("max_missing");
  });

  it("la scala ha un'etichetta visibile, «Cosa posso cucinare», anche a pannello chiuso", async () => {
    // dal giro: la scala «Tutte / Ora / +1 / +2 / +3» non aveva un'etichetta che si
    // vedesse; e resta fuori dal pannello dei filtri, sempre a video
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    expect(await screen.findByRole("group", { name: "Cosa posso cucinare" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Filtri" })).toHaveAttribute("aria-expanded", "false");
  });

  // Spec §11: «modello di embedding non caricato → la ricerca degrada a sola
  // ricerca testuale, con avviso discreto». Prima il degrado era invisibile: una
  // ricerca che trova solo le parole esatte ha lo stesso aspetto di una che capisce
  // il senso, e il difetto del Dockerfile che lo causava (C1) è stato invisibile
  // per tutto il branch proprio per questo.
  it("quando la ricerca è solo testuale lo dice, e non sembra un errore", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/search-mode")) return [{ semantic: false }, 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    expect(await screen.findByText(/solo testuale/i)).toBeDefined();
    // una constatazione, non un guasto: nessun ruolo d'allarme, e le ricette ci sono
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("Pasta al pomodoro")).toBeDefined();
  });

  it("quando la ricerca è ibrida non dice niente", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/search-mode")) return [{ semantic: true }, 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await screen.findByText("Pasta al pomodoro");
    expect(screen.queryByText(/solo testuale/i)).toBeNull();
  });

  it("se il modo di ricerca non risponde non mostra un avviso rotto", async () => {
    // un avviso su una cosa che forse funziona è peggio del silenzio, e il
    // ricettario deve restare utilizzabile
    stubRoutedFetch((path) => {
      if (path.includes("/search-mode")) return [{ detail: "giù" }, 500];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await screen.findByText("Pasta al pomodoro");
    expect(screen.queryByText(/solo testuale/i)).toBeNull();
  });

  // R2. Prima della soglia di `recipe_search.py` la graduatoria semantica conteneva
  // tutto il ricettario per qualunque query, quindi una ricerca non tornava mai
  // vuota e questa frase non si vedeva mai. Adesso può: e «Nessuna ricetta» è un
  // verdetto sul ricettario mentre il fatto riguarda le parole scritte.
  it("una ricerca senza riscontri parla delle parole, non del ricettario", async () => {
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.type(await screen.findByLabelText("Cerca nel ricettario"), "bulloni");

    expect(await screen.findByText(/Nessuna ricetta con queste parole/)).toBeDefined();
  });

  it("con il filtro acceso dice anche del filtro, che è l'altra cosa da togliere", async () => {
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Solo quelle che puoi cucinare adesso." })
    );
    await userEvent.type(screen.getByLabelText("Cerca nel ricettario"), "bulloni");

    // «fra quelle che puoi cucinare» appartiene solo al caso con entrambi: cercare
    // «togli il filtro» passerebbe anche sulla frase del solo filtro, che è quella
    // mostrata per i 180 ms del debounce, quando la query è ancora vuota
    expect(await screen.findByText(/fra quelle che puoi cucinare/)).toBeDefined();
  });

  it("col solo filtro acceso il vuoto parla della dispensa, non del ricettario", async () => {
    // dispensa vuota e filtro acceso: il ricettario è pieno, non c'è niente di
    // cucinabile. Senza questa frase il vuoto sembrerebbe colpa del ricettario, e
    // l'unica cosa da fare — togliere il filtro — non sarebbe nominata.
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Solo quelle che puoi cucinare adesso." })
    );

    expect(
      await screen.findByText(
        "Niente che puoi cucinare con quel che hai in dispensa: alza la soglia, o " +
          "scegli «Tutte» nella scala per vedere tutto il ricettario."
      )
    ).toBeDefined();
  });

  // Finding 1c della revisione finale: a un gradino di mezzo «alza la soglia» è
  // ancora un consiglio eseguibile, e deve comparire insieme a «Tutte».
  it("con un gradino di mezzo il vuoto offre sia di alzare la soglia sia «Tutte»", async () => {
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Al massimo 2 ingredienti da comprare." })
    );

    const messaggio = await screen.findByText(/Niente da cucinare comprando al massimo/);
    expect(messaggio.textContent).toMatch(/alza la soglia/);
    expect(messaggio.textContent).toMatch(/«Tutte» nella scala/);
  });

  // In cima alla scala non esiste un gradino più alto: «alza la soglia» sarebbe un
  // consiglio impossibile da seguire, non solo superfluo, ed è esattamente il tipo
  // di difetto che questo progetto tratta come tale invece che come una sfumatura.
  it("al gradino più alto il vuoto non consiglia di alzare la soglia, ma offre comunque una via d'uscita", async () => {
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Al massimo 3 ingredienti da comprare." })
    );

    const messaggio = await screen.findByText(/Niente da cucinare comprando al massimo/);
    expect(messaggio.textContent).not.toMatch(/alza la soglia/);
    expect(messaggio.textContent).toMatch(/«Tutte» nella scala/);
  });

  // Finding 1a: la casella «solo cucinabili» non esiste più, quindi il vuoto con
  // parole cercate più una soglia non può più dire «togli il filtro» — non c'è
  // nessun filtro da togliere, solo una scala da riportare a «Tutte».
  it("con parole cercate e una soglia il vuoto non parla più di un filtro da togliere", async () => {
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Al massimo 1 ingrediente da comprare." })
    );
    await userEvent.type(screen.getByLabelText("Cerca nel ricettario"), "bulloni");

    const messaggio = await screen.findByText(/Nessuna ricetta con queste parole/);
    expect(messaggio.textContent).not.toMatch(/togli il filtro/);
    expect(messaggio.textContent).toMatch(/«Tutte» nella scala/);
  });

  it("senza parole cercate il verdetto sul ricettario è quello giusto, e porta a «Nuova»", async () => {
    // l'unico caso in cui «il ricettario è vuoto» è vero: nessuna query, nessun filtro.
    // La via d'uscita è «Nuova» (T3 Consegna 4): l'AI non è più l'ingresso
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();

    expect(
      await screen.findByText("Il ricettario è vuoto: scrivi la prima ricetta con «Nuova».")
    ).toBeDefined();
    expect(screen.getByRole("heading", { name: "Nessuna ricetta" })).toBeInTheDocument();
    // senza filtri accesi non c'è niente da azzerare
    expect(screen.queryByRole("button", { name: "Azzera i filtri" })).toBeNull();
  });

  // Pattern 2 delle istruzioni: una ricerca fallita deve dirlo, non sembrare un
  // ricettario vuoto. Una ricerca semantica senza risultati ha esattamente lo
  // stesso aspetto di una ricerca rotta, quindi qui la distinzione conta di più.
  it("una ricerca fallita lo dice, e non sembra un ricettario vuoto", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    renderScreen();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/non sono riuscito/i);
    expect(screen.queryByText(/nessuna ricetta/i)).toBeNull();

    // il campo di ricerca resta utilizzabile: mai un vicolo cieco
    expect(screen.getByLabelText("Cerca nel ricettario")).not.toBeDisabled();
  });

  it("una ricerca fallita offre «Riprova», che riprova davvero", async () => {
    let giu = true;
    stubRoutedFetch((path) => {
      if (path.includes("/recipes/search?")) return giu ? [{ detail: "giù" }, 500] : [RESULTS, 200];
      return CODA_CON_CATEGORIE(path);
    });
    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Non sono riuscito a cercare nel ricettario."
    );
    giu = false;
    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));

    expect(await screen.findByText("Pasta all'aglio")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  // Pattern 3: una risposta lenta e superata non deve sovrascrivere una risposta
  // più recente e già arrivata. Stesso tipo di guardia costata un MAJOR nel
  // Task 18 per AddItemField, qui sulla ricerca del ricettario. La ricerca
  // sul montaggio (query vuota) deve risolversi per conto suo, quindi le due
  // ricerche in gara si distinguono dall'URL, non dall'ordine di chiamata.
  it("una risposta lenta e superata non sovrascrive quella più recente", async () => {
    let releaseSlow: (response: Response) => void = () => {};
    let releaseFast: (response: Response) => void = () => {};
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.includes("q=pollo")) {
        return new Promise<Response>((resolve) => { releaseSlow = resolve; });
      }
      if (href.includes("q=pesce")) {
        return new Promise<Response>((resolve) => { releaseFast = resolve; });
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderScreen();
    const field = await screen.findByLabelText("Cerca nel ricettario");

    await userEvent.type(field, "pollo");
    await vi.waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes("q=pollo"))).toBe(true)
    );

    await userEvent.clear(field);
    await userEvent.type(field, "pesce");
    await vi.waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes("q=pesce"))).toBe(true)
    );

    // la rapida arriva prima...
    releaseFast(new Response(JSON.stringify([riga("rf", "Risotto al pesce")]), { status: 200 }));
    expect(await screen.findByText("Risotto al pesce")).toBeDefined();

    // ...e quella lenta, superata, arriva dopo: non deve cambiare nulla
    releaseSlow(new Response(JSON.stringify([riga("rs", "Pollo al forno")]), { status: 200 }));
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(screen.getByText("Risotto al pesce")).toBeDefined();
    expect(screen.queryByText("Pollo al forno")).toBeNull();
  });

  it("una sessione scaduta durante la ricerca arriva alla QueryCache", async () => {
    // È il punto che App.tsx aggancia per riportare all'accesso. La prima versione
    // di questo schermo catturava il 401 in un .catch locale: l'utente leggeva
    // "ricerca fallita" e restava su uno schermo che non avrebbe mai più
    // funzionato, perché la sessione era finita e nessuno glielo diceva.
    const onError = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));

    renderScreen(new QueryCache({ onError }));

    await waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onError.mock.calls[0][0]).toBeInstanceOf(UnauthorizedError);
  });

  it("«Nuova» in alto porta al modulo di sempre; l'AI non è più l'ingresso", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    const nuova = await screen.findByRole("link", { name: "Nuova ricetta" });
    expect(nuova).toHaveAttribute("href", "/ricette/nuova-ai");
    // il nome accessibile comincia con la scritta a video (label-in-name)
    expect(nuova).toHaveTextContent("Nuova");
    expect(screen.queryByRole("link", { name: /Scrivi con l'AI/ })).toBeNull();
  });

  // Task 14, poi D3, poi T3 Consegna 4: la porta verso la coda c'è quando c'è davvero
  // qualcosa da decidere, col fondo ambra e il conteggio nella nota.
  it("quando ci sono ingredienti da abbinare, apre la porta verso la coda", async () => {
    const spy = vi.fn((url: unknown) => {
      const path = String(url);
      if (path.includes("/imports/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify(
              { fetched: 20, pending_recipes: 3, imported: 17, skipped: 0, pending_terms: 5 }
            ),
            { status: 200 }
          )
        );
      }
      if (path.includes("/recipes/categories")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(RESULTS), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();

    await screen.findByText(/5 ingredienti,/);
    const link = screen.getByRole("link", { name: /Ingredienti da abbinare/ });
    expect(link).toHaveClass("bg-low-tint");
    expect(link).toHaveTextContent(/3 ricette in attesa/);
    expect(link).toHaveAttribute("href", "/ricette/importa");
  });

  // "1 ingredienti da abbinare, 1 ricette in attesa" era il testo con un solo
  // termine e una sola ricetta in attesa: entrambi i plurali sbagliati a uno, lo
  // stesso caso che TermCard.tsx già tratta correttamente riga per riga.
  it("con un solo ingrediente e una sola ricetta usa il singolare per entrambi", async () => {
    const spy = vi.fn((url: unknown) => {
      const path = String(url);
      if (path.includes("/imports/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify(
              { fetched: 1, pending_recipes: 1, imported: 0, skipped: 0, pending_terms: 1 }
            ),
            { status: 200 }
          )
        );
      }
      if (path.includes("/recipes/categories")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(RESULTS), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();

    await screen.findByText("1 ingrediente, 1 ricetta in attesa");
    expect(screen.getByRole("link", { name: /Ingredienti da abbinare/ })).toHaveTextContent(
      "1 ingrediente, 1 ricetta in attesa"
    );
  });

  it("con la coda vuota la scheda non c'è: la coda si raggiunge dal ☰", async () => {
    // dal giro: la scheda stava in cima anche quando non c'era niente da decidere, e
    // spingeva la prima ricetta sotto la piega. La revisione delle decisioni già
    // prese resta raggiungibile da «Ingredienti da abbinare» nel ☰ (AppHeader)
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    await screen.findByText("Pasta al pomodoro");
    expect(screen.queryByRole("link", { name: /Ingredienti da abbinare/ })).toBeNull();
  });

  // «mai un vicolo cieco»: un conteggio che non arriva non si traveste da coda piena,
  // e il ricettario resta; la coda resta raggiungibile dal ☰
  it("se lo stato dell'import non arriva, la scheda non compare e il ricettario resta", async () => {
    const spy = vi.fn((url: unknown) => {
      const path = String(url);
      if (path.includes("/imports/status")) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: "giù" }), { status: 500 })
        );
      }
      if (path.includes("/recipes/categories")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(RESULTS), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();

    await screen.findByText("Pasta al pomodoro"); // la ricerca è arrivata comunque
    expect(screen.queryByRole("link", { name: /Ingredienti da abbinare/ })).toBeNull();
  });

  it("non riordina: l'ordine è quello che decide il backend", async () => {
    // L'ordinamento nasce da `recipe_search.py`, che mette davanti ciò a cui manca
    // meno. Una ricetta non cucinabile prima di una cucinabile è quindi un ordine
    // legittimo, e il frontend non deve "aggiustarlo": la logica di dominio sta nel
    // backend, ed è quella separazione che rende la porta a Capacitor un involucro.
    // Dati scelti perché *qualunque* riordino lato client cambi l'ordine: per
    // titolo crescente, per mancanti crescenti o per cucinabili prima, Agnello
    // finirebbe davanti. I primi dati che avevo scelto si ordinavano già così da
    // soli, e il test passava anche con un .sort() aggiunto: non aveva denti.
    const backendOrder = [
      riga("z", "Zuppa", { missing: 2, cookable: false, missing_names: ["Farro", "Porri"] }),
      riga("a", "Agnello"),
    ];
    stubRoutedFetch((path) => (path.includes("/recipes/categories") ? [[], 200] : [backendOrder, 200]));
    renderScreen();

    await screen.findByText("Zuppa");
    // dagli indirizzi delle righe: il primo `span` di una riga ora è la miniatura
    const righe = within(screen.getByRole("list", { name: "Ricette trovate" })).getAllByRole("link");
    expect(righe.map((link) => link.getAttribute("href"))).toEqual(["/ricette/z", "/ricette/a"]);
  });

  it("la miniatura mostra la foto, e la riga il tempo totale", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    const { container } = renderScreen();

    await screen.findByText("Pasta all'aglio");
    // la foto è decorativa (`alt=""`): il titolo è già il nome del collegamento
    const foto = container.querySelector('a[href="/ricette/r1"] img');
    expect(foto).toHaveAttribute("src", "https://example.com/aglio.jpg");
    expect(foto).toHaveAttribute("loading", "lazy");
    expect(screen.getByText("25 min")).toBeInTheDocument();
  });

  it("una ricetta senza foto e senza tempi non si rompe, e ha comunque la miniatura", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    const { container } = renderScreen();

    expect(await screen.findByText("Pasta al pomodoro")).toBeInTheDocument();
    const senzaFoto = container.querySelector('a[href="/ricette/r2"]')!;
    expect(senzaFoto.querySelector("img")).toBeNull();
    expect(senzaFoto.querySelector("[data-recipe-thumb] svg")).not.toBeNull();
  });

  // Il caso normale, non un'eccezione (spec §6.3): l'immagine viene dal server di
  // origine e non è mai copiata, quindi un 404 dopo un rinominamento a monte, un
  // blocco sul Referer o solo poco segnale in corridoio la fanno fallire. Senza
  // questa gestione la riga mostrerebbe un riquadro vuoto al posto della foto.
  it("una foto che non carica non lascia un buco: resta l'icona del reparto", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    const { container } = renderScreen();

    await screen.findByText("Pasta all'aglio");
    fireEvent.error(container.querySelector('a[href="/ricette/r1"] img')!);

    expect(container.querySelector('a[href="/ricette/r1"] img')).toBeNull();
    expect(container.querySelector('a[href="/ricette/r1"] [data-recipe-thumb] svg')).not.toBeNull();
    // il titolo resta una volta sola
    expect(screen.getAllByText("Pasta all'aglio")).toHaveLength(1);
  });

  it("i filtri stanno in un pannello chiuso, che «Filtri» apre e richiude", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    const filtri = await screen.findByRole("button", { name: "Filtri" });
    expect(filtri).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByLabelText("Contiene ingredienti")).not.toBeVisible();

    await userEvent.click(filtri);
    expect(filtri).toHaveAttribute("aria-expanded", "true");
    const campo = screen.getByLabelText("Contiene ingredienti");
    expect(campo).toBeVisible();
    // `aria-controls` nomina il pannello che contiene davvero i filtri
    expect(document.getElementById(filtri.getAttribute("aria-controls")!)).toContainElement(campo);

    await userEvent.click(filtri);
    expect(filtri).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByLabelText("Contiene ingredienti")).not.toBeVisible();
  });

  it("«Filtri» conta categoria e ingredienti, non le parole né la scala", async () => {
    stubRoutedFetch(CON_POMODORO);
    renderScreen();

    await userEvent.type(await screen.findByLabelText("Cerca nel ricettario"), "pasta");
    await userEvent.click(
      screen.getByRole("radio", { name: "Solo quelle che puoi cucinare adesso." })
    );
    expect(screen.getByRole("button", { name: "Filtri" })).toBeInTheDocument();

    await apriFiltri();
    await userEvent.selectOptions(await screen.findByLabelText("Categoria"), "Primi piatti");
    expect(screen.getByRole("button", { name: "Filtri, 1 attivo" })).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    // il numero si sente e si vede
    expect(screen.getByRole("button", { name: "Filtri, 2 attivi" })).toHaveTextContent("Filtri2");
  });

  it("il pannello dice quante ricette rispondono, col totale del server", async () => {
    stubRoutedFetch((path) =>
      path.includes("/recipes/search?")
        ? [RESULTS, 200, { "X-Total-Count": "42" }]
        : CODA_CON_CATEGORIE(path)
    );
    renderScreen();

    await apriFiltri();
    expect(await screen.findByText("42 ricette")).toBeVisible();
  });

  it("se il server dice che il totale è un minimo, il pannello dice «almeno»", async () => {
    // la piscina dei candidati di una ricerca a parole era piena (R-D, sesta lezione di
    // CLAUDE.md): altre ricette potrebbero rispondere e non sono state guardate, e un
    // «34 ricette» secco prometterebbe un conto che il server non ha fatto
    stubRoutedFetch((path) =>
      path.includes("/recipes/search?")
        ? [RESULTS, 200, { "X-Total-Count": "34", "X-Total-Count-Lower-Bound": "1" }]
        : CODA_CON_CATEGORIE(path)
    );
    renderScreen();

    await apriFiltri();
    expect(await screen.findByText("almeno 34 ricette")).toBeVisible();
    expect(screen.queryByText("34 ricette")).toBeNull();
  });

  it("«Azzera» toglie categoria e ingredienti, e lascia parole e scala", async () => {
    const fetchMock = stubRoutedFetch(CON_POMODORO);
    renderScreen();

    await userEvent.type(await screen.findByLabelText("Cerca nel ricettario"), "pasta");
    await userEvent.click(
      screen.getByRole("radio", { name: "Al massimo 2 ingredienti da comprare." })
    );
    await apriFiltri();
    await userEvent.selectOptions(await screen.findByLabelText("Categoria"), "Primi piatti");
    await userEvent.type(screen.getByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    await userEvent.click(screen.getByRole("button", { name: "Azzera" }));

    expect(screen.getByRole("button", { name: "Filtri" })).toBeInTheDocument();
    expect(screen.getByLabelText("Categoria")).toHaveValue("");
    expect(screen.queryByRole("button", { name: "Togli il filtro su Pomodoro" })).toBeNull();
    await waitFor(() => {
      const ultima = ultimaRicerca(fetchMock);
      expect(ultima).not.toContain("category=");
      expect(ultima).not.toContain("ingredient_id");
      expect(ultima).toContain("q=pasta");
      expect(ultima).toContain("max_missing=2");
    });
  });

  it("«Azzera» non c'è finché non c'è niente da azzerare", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    await apriFiltri();
    await screen.findByLabelText("Categoria");
    expect(screen.queryByRole("button", { name: "Azzera" })).toBeNull();
  });

  it("i filtri si ricordano finché l'app è aperta: rimontato, lo schermo li ritrova", async () => {
    // tornando da una ricetta lo schermo rinasce (Mattia, 2026-09-29)
    const fetchMock = stubRoutedFetch(CON_POMODORO);
    const primo = renderScreen();

    await userEvent.type(await screen.findByLabelText("Cerca nel ricettario"), "pasta");
    await userEvent.click(
      screen.getByRole("radio", { name: "Al massimo 1 ingrediente da comprare." })
    );
    await apriFiltri();
    await userEvent.selectOptions(await screen.findByLabelText("Categoria"), "Primi piatti");
    await userEvent.type(screen.getByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await screen.findByRole("button", { name: "Filtri, 2 attivi" });
    primo.unmount();

    renderScreen();

    expect(await screen.findByLabelText("Cerca nel ricettario")).toHaveValue("pasta");
    expect(
      screen.getByRole("radio", { name: "Al massimo 1 ingrediente da comprare." })
    ).toBeChecked();
    expect(screen.getByRole("button", { name: "Filtri, 2 attivi" })).toBeInTheDocument();
    await waitFor(() => {
      const ultima = ultimaRicerca(fetchMock);
      expect(ultima).toContain("q=pasta");
      expect(ultima).toContain("max_missing=1");
      expect(ultima).toContain("category=Primi+piatti");
      expect(ultima).toContain(`ingredient_id=${POMODORO.id}`);
    });
  });

  it("se la memoria non si legge né si scrive, si parte vuoti e il ricettario funziona", async () => {
    // finestra privata, dati del sito bloccati: il ricordo è una comodità
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloccata");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloccata");
    });
    const fetchMock = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    expect(await screen.findByText("Pasta all'aglio")).toBeInTheDocument();
    expect(screen.getByLabelText("Cerca nel ricettario")).toHaveValue("");
    await userEvent.type(screen.getByLabelText("Cerca nel ricettario"), "aglio");
    await waitFor(() => expect(ultimaRicerca(fetchMock)).toContain("q=aglio"));
  });

  it("il vuoto con dei filtri accesi offre «Azzera i filtri», che li toglie", async () => {
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      if (path.includes("/recipes/search?")) {
        return [path.includes("ingredient_id") ? [] : RESULTS, 200];
      }
      return [{ semantic: true }, 200];
    });
    renderScreen();

    await apriFiltri();
    await userEvent.type(await screen.findByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    expect(await screen.findByRole("heading", { name: "Nessuna ricetta" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Azzera i filtri" }));

    expect(await screen.findByText("Pasta all'aglio")).toBeInTheDocument();
    await waitFor(() => expect(ultimaRicerca(fetchMock)).not.toContain("ingredient_id"));
  });

  it("il filtro per categoria chiede al backend solo quella categoria", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    await apriFiltri();
    await userEvent.selectOptions(
      await screen.findByLabelText("Categoria"),
      "Dolci e Desserts"
    );

    await waitFor(() =>
      expect(
        spy.mock.calls.some(([url]) =>
          String(url).includes("category=Dolci+e+Desserts")
        )
      ).toBe(true)
    );
  });

  it("senza categorie nel ricettario il filtro non compare", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/recipes/categories")) return [[], 200];
      return CODA_CON_CATEGORIE(path);
    });
    renderScreen();

    await screen.findByText("Pasta all'aglio");
    await apriFiltri();
    expect(screen.getByLabelText("Contiene ingredienti")).toBeVisible();
    expect(screen.queryByLabelText("Categoria")).not.toBeInTheDocument();
  });

  it("scegliere un ingrediente filtra il ricettario su di lui", async () => {
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      // altrimenti il fallback finirebbe anche sotto /recipes/categories, e il
      // <select> tenterebbe di renderizzare ricette come opzioni
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await apriFiltri();
    await userEvent.type(await screen.findByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    await waitFor(() => {
      const ultima = fetchMock.mock.calls.map(([url]) => String(url)).filter((u) => u.includes("/recipes/search")).pop();
      expect(ultima).toContain(`ingredient_id=${POMODORO.id}`);
    });
    expect(screen.getByRole("button", { name: "Togli il filtro su Pomodoro" })).toBeDefined();
  });

  it("togliere il filtro riporta il ricettario intero", async () => {
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      // altrimenti il fallback finirebbe anche sotto /recipes/categories, e il
      // <select> tenterebbe di renderizzare ricette come opzioni
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await apriFiltri();
    await userEvent.type(await screen.findByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Togli il filtro su Pomodoro" }));

    await waitFor(() => {
      const ultima = fetchMock.mock.calls.map(([url]) => String(url)).filter((u) => u.includes("/recipes/search")).pop();
      expect(ultima).not.toContain("ingredient_id");
    });
  });

  it("nessun risultato con un ingrediente dice che è il filtro, non il ricettario", async () => {
    // stesso errore corretto in b6ed1d9 dall'altro lato dell'app: «nessuna ricetta»
    // è un verdetto sul ricettario, e quasi sempre riguarda il filtro
    stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      if (path.includes("/recipes/search")) return [[], 200];
      return [[], 200];
    });
    renderScreen();

    await apriFiltri();
    await userEvent.type(await screen.findByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(
      await screen.findByText(/Nessuna ricetta che contenga «Pomodoro»/)
    ).toBeDefined();
  });

  it("due ingredienti li chiede tutti e due, non solo l'ultimo scelto", async () => {
    // il parametro si ripete, e `set` al posto di `append` lascerebbe passare solo
    // l'ultimo: l'elenco a video sarebbe più largo di quello che il filtro promette,
    // e nessuno avrebbe modo di accorgersene se non contando le ricette
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO, BASILICO], 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await apriFiltri();
    const campo = await screen.findByLabelText("Contiene ingredienti");
    await userEvent.type(campo, "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await userEvent.type(campo, "basi");
    await userEvent.click(await screen.findByRole("option", { name: /Basilico/ }));

    await waitFor(() => {
      const ultima = ultimaRicerca(fetchMock);
      expect(ultima).toContain(`ingredient_id=${POMODORO.id}`);
      expect(ultima).toContain(`ingredient_id=${BASILICO.id}`);
    });
  });

  it("togliere un ingrediente lascia in piedi gli altri", async () => {
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO, BASILICO], 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await apriFiltri();
    const campo = await screen.findByLabelText("Contiene ingredienti");
    await userEvent.type(campo, "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await userEvent.type(campo, "basi");
    await userEvent.click(await screen.findByRole("option", { name: /Basilico/ }));
    await userEvent.click(screen.getByRole("button", { name: "Togli il filtro su Pomodoro" }));

    await waitFor(() => {
      const ultima = ultimaRicerca(fetchMock);
      expect(ultima).not.toContain(POMODORO.id);
      expect(ultima).toContain(`ingredient_id=${BASILICO.id}`);
    });
  });

  it("lo stesso ingrediente scelto due volte resta uno", async () => {
    // due volte lo stesso non stringe niente: sarebbe una pastiglia doppia da
    // togliere due volte, e una condizione ripetuta a vuoto nella query
    stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await apriFiltri();
    const campo = await screen.findByLabelText("Contiene ingredienti");
    await userEvent.type(campo, "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await userEvent.type(campo, "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(screen.getAllByRole("button", { name: "Togli il filtro su Pomodoro" })).toHaveLength(1);
  });

  it("senza risultati nomina tutti gli ingredienti chiesti, e dice che stringono", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO, BASILICO], 200];
      if (path.includes("/recipes/search")) return [[], 200];
      return [[], 200];
    });
    renderScreen();

    await apriFiltri();
    const campo = await screen.findByLabelText("Contiene ingredienti");
    await userEvent.type(campo, "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await userEvent.type(campo, "basi");
    await userEvent.click(await screen.findByRole("option", { name: /Basilico/ }));

    // entrambi nominati, e la via d'uscita è quella vera: togliere, non aggiungere
    expect(
      await screen.findByText(/Nessuna ricetta che contenga «Pomodoro» e «Basilico»/)
    ).toBeDefined();
    expect(screen.getByText(/togli un ingrediente/)).toBeDefined();
  });

  describe("«Mostra altre»", () => {
    function ricette(quante: number, da = 0) {
      return Array.from({ length: quante }, (_, n) => ({
        ...RESULTS[0], id: `r${da + n}`, title: `Ricetta ${da + n}`,
      }));
    }

    function paginato(path: string): Risposta {
      if (path.includes("/recipes/categories")) return [[], 200];
      if (path.includes("/recipes/search-mode")) return [{ semantic: true }, 200];
      const offset = Number(new URL(path, "http://x").searchParams.get("offset") ?? 0);
      // la seconda pagina ripete l'ultima della prima: è quel che fa un inserimento
      // sopra la pagina mentre l'import gira
      return offset === 0 ? [ricette(30), 200] : [ricette(5, 29), 200];
    }

    it("porta la pagina dopo, senza doppioni, e sparisce quando non ce ne sono altre", async () => {
      const fetchMock = stubRoutedFetch(paginato);
      renderScreen();
      await screen.findByText("Ricetta 29");

      await userEvent.click(screen.getByRole("button", { name: "Mostra altre" }));

      expect(await screen.findByText("Ricetta 33")).toBeDefined();
      expect(ultimaRicerca(fetchMock)).toContain("offset=30");
      expect(screen.getAllByText("Ricetta 29")).toHaveLength(1);
      expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
    });

    it("chiede sempre la stessa misura di pagina che usa per decidere se ce n'è un'altra", async () => {
      const fetchMock = stubRoutedFetch(paginato);
      renderScreen();
      await screen.findByText("Ricetta 29");
      expect(ultimaRicerca(fetchMock)).toContain("limit=30");
    });

    it("con meno di una pagina non la offre", async () => {
      stubRoutedFetch(CODA_CON_CATEGORIE);
      renderScreen();
      await screen.findByText("Pasta all'aglio");
      expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
    });

    // Col totale del server (T3 Consegna 4) «Mostra altre» sa se ne mancano: prima una
    // pagina piena che era anche l'ultima offriva un tocco che portava una pagina vuota.
    it("col totale del server, «Mostra altre» c'è finché non sono arrivate tutte", async () => {
      stubRoutedFetch((path) => {
        const [body, status] = paginato(path);
        return path.includes("/recipes/search?")
          ? [body, status, { "X-Total-Count": "34" }]
          : [body, status];
      });
      renderScreen();
      await screen.findByText("Ricetta 29");

      await userEvent.click(screen.getByRole("button", { name: "Mostra altre" }));

      expect(await screen.findByText("Ricetta 33")).toBeDefined();
      expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
    });

    it("col totale del server, una pagina piena che è anche l'ultima non la offre", async () => {
      stubRoutedFetch((path) =>
        path.includes("/recipes/search?")
          ? [ricette(30), 200, { "X-Total-Count": "30" }]
          : paginato(path)
      );
      renderScreen();
      await screen.findByText("Ricetta 29");
      expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
    });

    it("se la pagina dopo fallisce, le ricette restano e si può riprovare", async () => {
      stubRoutedFetch((path) => {
        if (path.includes("offset=30")) return [{ detail: "giù" }, 500];
        return paginato(path);
      });
      renderScreen();
      await screen.findByText("Ricetta 29");

      await userEvent.click(screen.getByRole("button", { name: "Mostra altre" }));

      expect(await screen.findByText("Non sono riuscito a caricarne altre.")).toBeDefined();
      expect(screen.getByText("Ricetta 0")).toBeDefined();
      expect(screen.queryByText(/Non sono riuscito a cercare/)).toBeNull();
      expect(screen.getByRole("button", { name: "Mostra altre" })).toBeDefined();
    });
  });
});
