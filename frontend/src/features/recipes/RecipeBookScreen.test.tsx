import { describe, expect, it, vi, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RecipeBookScreen } from "./RecipeBookScreen";
import { UnauthorizedError } from "../../api/client";

const POMODORO = { id: "i9", name: "pomodoro", display_name: "Pomodoro", category: "verdura" };
const BASILICO = { id: "i7", name: "basilico", display_name: "Basilico", category: "verdura" };

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
    prep_minutes: 10, cook_minutes: 15, category: "Primi piatti" },
  { id: "r2", title: "Pasta al pomodoro", description: "Di sempre", source: "ai",
    missing: 1, cookable: false, missing_names: ["Pomodoro"], image_url: null,
    prep_minutes: null, cook_minutes: null, category: null },
];

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

// Nessun ingrediente in attesa: la scheda d'ingresso verso la coda resta (D3), ma
// tranquilla — senza ambra né conteggio in sospeso — nei test che non la riguardano.
const NESSUN_IMPORT_IN_CORSO = {
  fetched: 0, pending_recipes: 0, imported: 0, skipped: 0, pending_terms: 0,
};

/** Un fetch che risponde in base al percorso: lo schermo fa tre chiamate — la
 * ricerca, il modo di ricerca e lo stato dell'import — e ognuna deve ricevere una
 * Response nuova, perché il corpo di una Response si legge una volta sola. */
function stubRoutedFetch(route: (path: string) => [unknown, number]) {
  const spy = vi.fn((url: unknown) => {
    const path = String(url);
    const [body, status] = path.includes("/imports/status")
      ? [NESSUN_IMPORT_IN_CORSO, 200]
      : route(path);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const CODA_CON_CATEGORIE = (path: string): [unknown, number] => {
  if (path.includes("/recipes/categories")) return [["Primi piatti", "Dolci e Desserts"], 200];
  if (path.includes("/recipes/search-mode")) return [{ semantic: true }, 200];
  return [RESULTS, 200];
};

describe("RecipeBookScreen", () => {
  it("mostra la provenienza di ogni ricetta", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    expect(await screen.findByText("dataset")).toBeDefined();
    expect(screen.getByText("AI")).toBeDefined();
  });

  it("dice quanto manca, senza nascondere la ricetta", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    expect(await screen.findByText("Pasta al pomodoro")).toBeDefined();
    expect(screen.getByText("manca 1 ingrediente")).toBeDefined();
  });

  it("segnala le ricette che puoi cucinare adesso", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    expect(await screen.findByText("Puoi cucinarla ora")).toBeDefined();
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
          "scegli «Tutte» per vedere tutto il ricettario."
      )
    ).toBeDefined();
  });

  it("senza parole cercate il verdetto sul ricettario è quello giusto", async () => {
    // l'unico caso in cui «Nessuna ricetta» è vero: nessuna query, nessun filtro
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();

    expect(await screen.findByText("Nessuna ricetta. Provane una scritta con l'AI."))
      .toBeDefined();
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
    releaseFast(new Response(JSON.stringify([
      { id: "rf", title: "Risotto al pesce", description: null, source: "dataset",
        missing: 0, cookable: true },
    ]), { status: 200 }));
    expect(await screen.findByText("Risotto al pesce")).toBeDefined();

    // ...e quella lenta, superata, arriva dopo: non deve cambiare nulla
    releaseSlow(new Response(JSON.stringify([
      { id: "rs", title: "Pollo al forno", description: null, source: "dataset",
        missing: 0, cookable: true },
    ]), { status: 200 }));
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

  // Task 14, poi D3 (Task 3 di cinque-voci): la porta verso la coda di revisione
  // è sempre presente — vedi il test più sotto — e quando c'è davvero qualcosa da
  // decidere prende il fondo ambra e il conteggio nella nota.
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

  it("l'ingresso agli ingredienti da abbinare resta anche con la coda vuota", async () => {
    // prima spariva: la revisione delle decisioni già prese diventava irraggiungibile
    // proprio quando non c'era più niente da decidere
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    await screen.findByText("Pasta al pomodoro");
    const link = screen.getByRole("link", { name: /Ingredienti da abbinare/ });
    expect(link.getAttribute("href")).toBe("/ricette/importa");
    expect(link).not.toHaveClass("bg-low-tint");
    expect(link).toHaveTextContent("Niente in attesa: qui si rivedono le decisioni già prese");
  });

  // D3/CLAUDE.md, «mai un vicolo cieco»: un conteggio che non arriva toglie la
  // nota, non la strada. La ricerca risponde normalmente, solo /imports/status
  // fallisce con un 500.
  it("se lo stato dell'import non arriva, la porta alla coda resta con una nota generica", async () => {
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
    const link = screen.getByRole("link", { name: /Ingredienti da abbinare/ });
    expect(link.getAttribute("href")).toBe("/ricette/importa");
    expect(link).not.toHaveClass("bg-low-tint");
    expect(link).toHaveTextContent("Le decisioni dell'import, da rivedere");
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
      { id: "z", title: "Zuppa", description: null, source: "dataset",
        missing: 2, cookable: false },
      { id: "a", title: "Agnello", description: null, source: "dataset",
        missing: 0, cookable: true },
    ];
    stubRoutedFetch((path) => (path.includes("/recipes/categories") ? [[], 200] : [backendOrder, 200]));
    renderScreen();

    await screen.findByText("Zuppa");
    const titles = screen
      .getAllByRole("listitem")
      .map((li) => li.querySelector("span")?.textContent);
    expect(titles).toEqual(["Zuppa", "Agnello"]);
  });

  it("mostra la foto e il tempo totale quando ci sono", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    const foto = await screen.findByRole("img", { name: "Pasta all'aglio" });
    expect(foto).toHaveAttribute("loading", "lazy");
    expect(screen.getByText("25 min")).toBeInTheDocument();
  });

  it("una ricetta senza foto e senza tempi non si rompe", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    expect(await screen.findByText("Pasta al pomodoro")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Pasta al pomodoro" })).not.toBeInTheDocument();
  });

  // Il caso normale, non un'eccezione (spec §6.3): l'immagine viene dal server di
  // origine e non è mai copiata, quindi un 404 dopo un rinominamento a monte, un
  // blocco sul Referer o solo poco segnale in corridoio la fanno fallire. Senza
  // questa gestione la scheda mostra il titolo due volte (l'alt dell'immagine
  // rotta, e il titolo vero sotto) più un riquadro vuoto delle dimensioni della
  // foto mancata — ~230px su 812.
  it("una foto che non carica non lascia un buco: la scheda torna al layout senza foto", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    const foto = await screen.findByRole("img", { name: "Pasta all'aglio" });
    fireEvent.error(foto);

    expect(screen.queryByRole("img", { name: "Pasta all'aglio" })).not.toBeInTheDocument();
    // il titolo resta una volta sola: non si duplica nell'alt di un'immagine ormai
    // fuori pagina
    expect(screen.getAllByText("Pasta all'aglio")).toHaveLength(1);
  });

  it("il filtro per categoria chiede al backend solo quella categoria", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

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
});
