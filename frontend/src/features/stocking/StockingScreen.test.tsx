import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { StockingScreen } from "./StockingScreen";
import { UnauthorizedError } from "../../api/client";

const CHECKED = [
  { id: "s1", raw_text: "yogurt greco", ingredient_id: "i1", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", status: "checked", reason: "manual",
    created_at: "2026-09-11T10:00:00Z" },
  { id: "s2", raw_text: "mele", ingredient_id: "i2", ingredient_name: "mela",
    ingredient_category: "frutta", status: "checked", reason: "manual",
    created_at: "2026-09-11T10:05:00Z" },
];

// "un ingrediente che risolve a niente": una voce spuntata senza ingredient_id,
// perché il testo libero non ha mai trovato un corrispondente. Non deve sparire
// in silenzio: deve restare sistemabile a mano, abbinando un ingrediente.
const UNMATCHED = [
  { id: "s3", raw_text: "cosa strana", ingredient_id: null, ingredient_name: null,
    ingredient_category: null, status: "checked", reason: "manual",
    created_at: "2026-09-11T10:10:00Z" },
];

const STRANGE = { id: "i9", name: "cosa strana", display_name: "Cosa Strana", category: "altro" };

// Un suggerimento che la ricerca tira dentro per un frammento e basta: in
// produzione «cera per pavimenti» ne pescava sette così, `Pera` in testa con
// 0.278, agganciata su «p*era*» e su «*per*». Nessuno pertinente, tutti sopra
// SIMILARITY_FLOOR.
const PERA = { id: "i7", name: "pera", display_name: "Pera", category: "frutta" };

// Lo yogurt che si ricompra ogni settimana: già in catalogo con marca e nutrienti,
// e l'unico modo di riagganciarlo era riscansionare il codice a barre.
const FAGE = {
  id: "p1", ingredient_id: "i1", name: "Total 0%", brand: "Fage", barcode: "52010",
  source: "openfoodfacts", nutrients: { kcal: 57 }, image_url: null,
};
// stesso nome, ingrediente diverso: la coppia (ingrediente, prodotto) che il
// backend respinge con 409, e che nessuna delle due strade deve poter costruire
const OTHER_INGREDIENT_PRODUCT = {
  ...FAGE, id: "p2", ingredient_id: "i9", name: "Total 0% magro",
};

function renderScreen(client?: QueryClient) {
  const queryClient =
    client ??
    new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <StockingScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

/** Un fetch che risponde in base al percorso: ogni chiamata riceve una Response
 * nuova, perché il corpo di una Response si può leggere una volta sola. */
function stubRoutedFetch(route: (path: string, init?: RequestInit) => [unknown, number?]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    return Promise.resolve(respond(body, status ?? 200));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function postBody(spy: ReturnType<typeof stubRoutedFetch>, suffix: string) {
  const call = spy.mock.calls.find(
    ([url, init]) => String(url).endsWith(suffix) && (init as RequestInit)?.method === "POST"
  );
  return JSON.parse(String((call?.[1] as RequestInit).body));
}

describe("StockingScreen", () => {
  it("elenca solo le voci spuntate", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(CHECKED)));
    renderScreen();
    expect(await screen.findByText("yogurt greco")).toBeDefined();
    expect(screen.getByText("mele")).toBeDefined();
  });

  it("permette di confermare una voce come sfusa, senza prodotto", async () => {
    const spy = vi.fn()
      .mockResolvedValueOnce(respond(CHECKED))
      .mockResolvedValue(respond({ created: 1 }, 201));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
    await userEvent.click(screen.getByRole("button", { name: /Metti in dispensa/ }));

    const post = spy.mock.calls.find(([url]) => String(url).endsWith("/shopping-list/stock"));
    expect(JSON.parse(post?.[1].body).entries).toEqual([
      { shopping_item_id: "s2", ingredient_id: "i2", product_id: null, expires_on: null },
    ]);
  });

  it("un codice a barre noto aggancia subito il prodotto di catalogo", async () => {
    const lookup = {
      found: true, origin: "catalog", suggestion: null,
      product: { id: "p1", ingredient_id: "i1", name: "Total 0%", brand: "Fage",
                 barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null },
    };
    const spy = vi.fn()
      .mockResolvedValueOnce(respond(CHECKED))
      .mockResolvedValue(respond(lookup));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    // lo scanner in ambiente di test non legge: il campo manuale copre il caso
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010{Enter}");

    expect(await screen.findByText("Total 0%")).toBeDefined();
  });

  it("un codice ignoto apre la creazione manuale invece di un errore", async () => {
    const spy = vi.fn()
      .mockResolvedValueOnce(respond(CHECKED))
      .mockResolvedValue(respond({ found: false, origin: "unknown", product: null,
                                   suggestion: null }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    await userEvent.type(screen.getByLabelText("Codice a barre"), "000{Enter}");

    expect(await screen.findByRole("heading", { name: /Nuovo prodotto/ })).toBeDefined();
  });

  it("un suggerimento di Open Food Facts precompila il modulo, non lo lascia vuoto", async () => {
    // la fiche esiste, solo non è ancora in catalogo: buttarla via e far
    // ridigitare tutto da zero sarebbe un mezzo vicolo cieco
    const lookup = {
      found: true, origin: "openfoodfacts", product: null,
      suggestion: { name: "Passata Rustica", brand: "Mutti", barcode: "88990",
                    nutrients: { kcal: 30 }, image_url: null },
    };
    const spy = vi.fn()
      .mockResolvedValueOnce(respond(CHECKED))
      .mockResolvedValue(respond(lookup));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    await userEvent.type(screen.getByLabelText("Codice a barre"), "88990{Enter}");

    await screen.findByRole("heading", { name: /Nuovo prodotto/ });
    expect(screen.getByLabelText("Nome")).toHaveValue("Passata Rustica");
    expect(screen.getByLabelText("Marca")).toHaveValue("Mutti");
    expect(screen.getByLabelText("Calorie per 100 g")).toHaveValue(30);
  });

  // M3, spec §8.2 strada 2. `searchProducts` esisteva e non era chiamata da
  // nessuna parte: l'unica strada per un prodotto noto era il codice a barre, che
  // non si legge se la confezione è aperta o il codice è rovinato, e «sfuso» perde
  // la marca e con essa i nutrienti.
  it("un prodotto già in catalogo si aggancia cercandolo per nome", async () => {
    const spy = stubRoutedFetch((path) => {
      if (path.includes("/products/search")) return [[FAGE]];
      if (path.includes("/shopping-list/stock")) return [{ created: 1 }, 201];
      return [CHECKED];
    });

    renderScreen();
    await userEvent.click(
      await screen.findByRole("button", { name: /Cerca a catalogo.*yogurt greco/i })
    );
    await userEvent.click(await screen.findByRole("option", { name: /Total 0%/ }));
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa" }));

    expect(postBody(spy, "/stock").entries).toEqual([
      { shopping_item_id: "s1", ingredient_id: "i1", product_id: "p1", expires_on: null },
    ]);
  });

  it("il termine di ricerca arriva al backend, per affinare aggiungendo parole", async () => {
    const spy = stubRoutedFetch((path) =>
      path.includes("/products/search") ? [[FAGE]] : [CHECKED]
    );

    renderScreen();
    await userEvent.click(
      await screen.findByRole("button", { name: /Cerca a catalogo.*yogurt greco/i })
    );
    await userEvent.type(screen.getByLabelText("Cerca a catalogo"), " pesca");

    await vi.waitFor(() =>
      expect(
        spy.mock.calls.some(([url]) =>
          String(url).includes("/products/search?q=yogurt%20greco%20pesca")
        )
      ).toBe(true)
    );
  });

  // Il backend respinge con 409 la coppia (ingrediente, prodotto) incoerente, e la
  // sistemazione è tutto-o-niente: una scelta sbagliata offerta qui e confermata
  // farebbe fallire l'intero giro di spesa. Il filtro c'è perché rifiutare dopo
  // aver confermato è peggio che non offrire una scelta che non si può accettare.
  it("un prodotto di un altro ingrediente non si può agganciare a questa voce", async () => {
    stubRoutedFetch((path) =>
      path.includes("/products/search") ? [[FAGE, OTHER_INGREDIENT_PRODUCT]] : [CHECKED]
    );

    renderScreen();
    await userEvent.click(
      await screen.findByRole("button", { name: /Cerca a catalogo.*yogurt greco/i })
    );

    expect(await screen.findByRole("option", { name: /Total 0% Fage/ })).toBeDefined();
    expect(screen.queryByRole("option", { name: /magro/ })).toBeNull();
    // e il motivo è scritto: senza, sembrerebbe che il catalogo non lo conosca
    expect(screen.getByText(/di un altro ingrediente/)).toBeDefined();
  });

  // R1, l'altra metà dello stesso fatto. `GET /products/barcode/{code}` cerca per
  // codice e basta: la referenza che torna può essere di un altro ingrediente
  // («Passata Mutti» creata sotto `pomodoro`, riletta su una voce risolta a
  // `passata`). Adottarla faceva fallire con 409 tutta la sistemazione, comprese le
  // voci giuste, e riprovare rimandava lo stesso corpo: 409 per sempre.
  it("un codice a barre di un altro ingrediente non si aggancia, e non parte nessuna richiesta", async () => {
    const spy = stubRoutedFetch((path) =>
      path.includes("/products/barcode/") ? [{ found: true, origin: "catalog",
        suggestion: null, product: OTHER_INGREDIENT_PRODUCT }] : [CHECKED]
    );

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010{Enter}");

    // non `findByRole("alert")`: in jsdom senza fotocamera lo scanner ha già il suo
    // avviso di degradazione, e i due ruoli sarebbero ambigui
    expect(await screen.findByText(/di un altro ingrediente/)).toBeDefined();
    // la voce non è risolta: le tre strade sono ancora tutte aperte, e il pulsante
    // della sistemazione resta spento, cioè il 409 non è raggiungibile da qui
    expect(screen.getByRole("button", { name: /Sfuso.*yogurt greco/i })).toBeDefined();
    expect(screen.getByRole("button", { name: "Metti in dispensa" })).toBeDisabled();
    expect(spy.mock.calls.some(([url]) => String(url).endsWith("/shopping-list/stock"))).toBe(
      false
    );
  });

  it("una conferma sbagliata si disfà con «Cambia», senza perdere le altre", async () => {
    // prima di R1 non c'era nessun modo di cambiare la risoluzione di una riga: i
    // tre pulsanti stanno sotto `!resolution` e nessuno cancellava la chiave.
    // L'unica uscita era navigare via, cioè perdere le conferme di tutto il giro.
    const spy = stubRoutedFetch((path) => {
      if (path.includes("/products/barcode/")) {
        return [{ found: true, origin: "catalog", suggestion: null, product: FAGE }];
      }
      if (path.includes("/shopping-list/stock")) return [{ created: 1 }, 201];
      return [CHECKED];
    });

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010{Enter}");
    expect(await screen.findByText("Total 0%")).toBeDefined();
    await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));

    await userEvent.click(screen.getByRole("button", { name: /Cambia.*yogurt greco/i }));

    // la riga torna da scegliere, e quella delle mele resta confermata
    expect(screen.getByRole("button", { name: /Sfuso.*yogurt greco/i })).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa" }));
    await vi.waitFor(() =>
      expect(postBody(spy, "/shopping-list/stock").entries).toEqual([
        { shopping_item_id: "s2", ingredient_id: "i2", product_id: null, expires_on: null },
      ])
    );
  });

  it("una sistemazione fallita dice cosa fare, non «riprova» quando riprovare non può riuscire", async () => {
    // la rotta è tutto-o-niente: su un 404 lo stesso corpo rimandato dà lo stesso
    // errore per sempre, quindi «riprova» era un vicolo cieco
    stubRoutedFetch((path) =>
      path.includes("/shopping-list/stock") ? [{ detail: "voce di lista inesistente" }, 404]
        : [CHECKED]
    );

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa" }));

    const avviso = await screen.findByRole("alert");
    expect(avviso).toHaveTextContent(/non esiste più/);
    expect(avviso).toHaveTextContent(/non ho messo in dispensa niente/i);
    expect(screen.getByRole("button", { name: /Rileggi la spesa/ })).toBeDefined();
  });

  it("un catalogo senza riscontri non è un muro: si crea il prodotto a mano", async () => {
    stubRoutedFetch((path) => (path.includes("/products/search") ? [[]] : [CHECKED]));

    renderScreen();
    await userEvent.click(
      await screen.findByRole("button", { name: /Cerca a catalogo.*yogurt greco/i })
    );

    expect(await screen.findByText(/Nessun prodotto con queste parole/)).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: "Crea il prodotto a mano" }));
    expect(screen.getByRole("heading", { name: /Nuovo prodotto per «yogurt greco»/ }))
      .toBeDefined();
  });

  it("un 401 sulla ricerca a catalogo arriva alla QueryCache, come ogni altra ricerca", async () => {
    const onError = vi.fn();
    stubRoutedFetch((path) =>
      path.includes("/products/search") ? [{ detail: "fuori" }, 401] : [CHECKED]
    );
    const client = new QueryClient({
      queryCache: new QueryCache({ onError }),
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    renderScreen(client);
    await userEvent.click(
      await screen.findByRole("button", { name: /Cerca a catalogo.*yogurt greco/i })
    );

    await vi.waitFor(() => expect(onError).toHaveBeenCalled());
    expect(
      onError.mock.calls.some(([error]) => error instanceof UnauthorizedError)
    ).toBe(true);
  });

  it("non manda in dispensa nulla se non hai confermato niente", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(CHECKED)));
    renderScreen();
    await screen.findByText("mele");
    expect(screen.getByRole("button", { name: /Metti in dispensa/ })).toBeDisabled();
  });

  it("una lista che non si carica non viene spacciata per una lista vuota", async () => {
    // tornando dalla spesa con le borse in mano, "non hai spuntato niente" è una
    // bugia: un caricamento fallito va detto, con una riprova
    stubRoutedFetch(() => [{ detail: "giù" }, 500]);

    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent(/non sono riuscito a caricare/i);
    expect(screen.queryByText(/Niente da sistemare/)).toBeNull();
    expect(screen.getByRole("button", { name: "Riprova" })).toBeDefined();
  });

  it("un lookup fallito lo dice e offre la creazione a mano", async () => {
    // il muro più silenzioso: rete giù, Invio, e non succedeva niente
    const spy = stubRoutedFetch((path) =>
      path.includes("/products/barcode/") ? [{ detail: "giù" }, 500] : [CHECKED]
    );

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010{Enter}");

    // lo scanner, in jsdom senza fotocamera, ha già il suo alert di degradazione:
    // quello che conta qui è che il lookup fallito dica la sua
    expect(await screen.findByText(/non sono riuscito a leggere il codice/i)).toBeDefined();
    // e il codice digitato resta nel campo: un lookup fallito non deve far
    // perdere quel che l'utente ha scritto (la regola di Task 18)
    expect(screen.getByLabelText("Codice a barre")).toHaveValue("52010");

    await userEvent.click(screen.getByRole("button", { name: /Crea il prodotto a mano/i }));

    expect(await screen.findByRole("heading", { name: /Nuovo prodotto per «yogurt greco»/ }))
      .toBeDefined();
    expect(spy).toHaveBeenCalled();
  });

  it("un 401 sul lookup passa dalla MutationCache, come ogni altra chiamata", async () => {
    // fuori da react-query, una sessione scaduta qui non riportava all'accesso
    const onError = vi.fn();
    const client = new QueryClient({
      mutationCache: new MutationCache({ onError }),
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    stubRoutedFetch((path) =>
      path.includes("/products/barcode/") ? ["", 401] : [CHECKED]
    );

    renderScreen(client);
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010{Enter}");

    await vi.waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onError.mock.calls[0][0]).toBeInstanceOf(UnauthorizedError);
  });

  it("il campo del codice non conserva il codice della voce precedente", async () => {
    // il residuo agganciava alle mele il prodotto dello yogurt, senza una conferma
    stubRoutedFetch((path) =>
      path.includes("/products/barcode/")
        ? [{ found: false, origin: "unknown", product: null, suggestion: null }]
        : [CHECKED]
    );

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    await userEvent.type(screen.getByLabelText("Codice a barre"), "111{Enter}");
    await screen.findByRole("heading", { name: /Nuovo prodotto/ });

    await userEvent.click(screen.getByRole("button", { name: /Codice.*mele/i }));

    expect(screen.getByLabelText("Codice a barre")).toHaveValue("");
  });

  it("il modulo non si ricicla fra due voci, con i dati della prima", async () => {
    // riusare l'istanza salvava "Passata Rustica" sotto l'ingrediente mela
    stubRoutedFetch((path) => {
      if (path.endsWith("/products/barcode/111")) {
        return [{ found: true, origin: "openfoodfacts", product: null,
                  suggestion: { name: "Passata Rustica", brand: "Mutti", barcode: "111",
                                nutrients: { kcal: 30 }, image_url: null } }];
      }
      if (path.includes("/products/barcode/")) {
        return [{ found: false, origin: "unknown", product: null, suggestion: null }];
      }
      return [CHECKED];
    });

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    await userEvent.type(screen.getByLabelText("Codice a barre"), "111{Enter}");
    expect(await screen.findByLabelText("Nome")).toHaveValue("Passata Rustica");

    await userEvent.click(screen.getByRole("button", { name: /Codice.*mele/i }));
    await userEvent.type(screen.getByLabelText("Codice a barre"), "222{Enter}");

    await screen.findByRole("heading", { name: /Nuovo prodotto per «mele»/ });
    expect(screen.getByLabelText("Nome")).toHaveValue("");
    expect(screen.getByLabelText("Calorie per 100 g")).toHaveValue(null);
  });

  it("una voce senza ingrediente abbinato si sistema abbinandone uno a mano", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (path.includes("/ingredients/search")) return [[STRANGE]];
      if (path.endsWith("/shopping-list/stock") && init?.method === "POST") {
        return [{ created: 1 }, 201];
      }
      return [UNMATCHED];
    });

    renderScreen();
    await screen.findByText("cosa strana");

    // niente pulsanti di sistemazione finché la voce non ha un ingrediente:
    // comparirebbero comandi che alla conferma sparirebbero in silenzio
    expect(screen.queryByRole("button", { name: /Sfuso/i })).toBeNull();

    const matchField = screen.getByLabelText(/Abbina un ingrediente/i);
    await userEvent.type(matchField, "strana");

    await userEvent.click(await screen.findByRole("option", { name: /Cosa Strana/i }));
    await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*cosa strana/i }));
    await userEvent.click(screen.getByRole("button", { name: /Metti in dispensa/ }));

    // l'abbinamento fatto a mano deve arrivare davvero nel POST: è il punto di
    // tutto il percorso, ed è esattamente ciò che prima spariva in silenzio
    await vi.waitFor(() =>
      expect(postBody(spy, "/shopping-list/stock").entries).toEqual([
        { shopping_item_id: "s3", ingredient_id: "i9", product_id: null, expires_on: null },
      ])
    );
  });

  it("se nessun ingrediente corrisponde lo dice, e lascia crearlo", async () => {
    // è il caso normale per un testo spaiato: cercare lo stesso testo che non ha
    // trovato niente non troverà niente neanche ora
    const spy = stubRoutedFetch((path, init) => {
      if (path.includes("/ingredients/search")) return [[]];
      if (path.endsWith("/ingredients") && init?.method === "POST") return [STRANGE, 201];
      return [UNMATCHED];
    });

    renderScreen();
    await screen.findByText("cosa strana");

    expect(
      await screen.findByText(
        "Nessun ingrediente corrisponde. Puoi crearlo adesso: scegli il reparto e la voce " +
          "diventa sistemabile."
      )
    ).toBeDefined();
    // non tocca il <select>: è la prova che chi non sceglie niente ottiene
    // esattamente quel che otteneva prima, cioè "altro"
    await userEvent.click(screen.getByRole("button", { name: /Crea l'ingrediente/i }));

    expect(await screen.findByRole("button", { name: /Sfuso.*cosa strana/i })).toBeDefined();
    expect(postBody(spy, "/ingredients")).toEqual({
      name: "cosa strana",
      display_name: "cosa strana",
      category: "altro",
    });
  });

  it("il reparto di una voce nuova si sceglie, e fra i reparti c'è anche il non alimentare", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (path.includes("/ingredients/search")) return [[]];
      if (path.endsWith("/ingredients") && init?.method === "POST") return [STRANGE, 201];
      return [UNMATCHED];
    });

    renderScreen();
    await screen.findByText("cosa strana");

    const reparto = await screen.findByLabelText("Reparto");
    // il non alimentare è offerto: è l'unico modo perché un detersivo entri in
    // dispensa senza passare per «altro», che è il reparto delle cose da chiarire
    expect(
      [...(reparto as HTMLSelectElement).options].map((o) => o.value)
    ).toContain("casa");

    await userEvent.selectOptions(reparto, "casa");
    await userEvent.click(screen.getByRole("button", { name: /Crea l'ingrediente/i }));

    expect(postBody(spy, "/ingredients")).toEqual({
      name: "cosa strana",
      display_name: "cosa strana",
      category: "casa",
    });
  });

  it("la creazione resta raggiungibile anche quando la ricerca trova qualcosa", async () => {
    // Il difetto misurato in produzione il 2026-09-18: la porta stava dietro
    // `suggestions.length === 0`, cioè bastava un suggerimento qualsiasi — anche
    // «Pera» per «cera per pavimenti» — e l'unico posto dell'app che crea un
    // ingrediente spariva, lasciando la voce in lista per sempre.
    const spy = stubRoutedFetch((path, init) => {
      if (path.includes("/ingredients/search")) return [[PERA]];
      if (path.endsWith("/ingredients") && init?.method === "POST") return [STRANGE, 201];
      return [UNMATCHED];
    });

    renderScreen();
    await screen.findByText("cosa strana");

    // il suggerimento c'è e resta: la correzione non sta nella ricerca
    expect(await screen.findByRole("option", { name: /Pera/i })).toBeDefined();
    // ...ma non è più lui a decidere se si può creare
    await userEvent.selectOptions(await screen.findByLabelText("Reparto"), "casa");
    await userEvent.click(screen.getByRole("button", { name: /Crea l'ingrediente/i }));

    expect(postBody(spy, "/ingredients")).toEqual({
      name: "cosa strana",
      display_name: "cosa strana",
      category: "casa",
    });
    // la frase del caso vuoto resta al caso vuoto: davanti a un suggerimento
    // «nessun ingrediente corrisponde» sarebbe falso
    expect(screen.queryByText(/Nessun ingrediente corrisponde/)).toBeNull();
  });

  it("il campo della scadenza non c'è finché non lo si chiede", async () => {
    // dieci campi vuoti a video sono rumore permanente per chi la scadenza non la
    // scrive mai, e questo è già lo schermo più denso dell'app
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(CHECKED)));
    renderScreen();

    await screen.findByText("yogurt greco");
    expect(screen.queryByLabelText(/scadenza/i)).toBeNull();

    await user.click(screen.getAllByRole("button", { name: /scadenza/i })[0]);
    expect(screen.getByLabelText(/scadenza di yogurt greco/i)).toBeDefined();
  });

  it("una data scritta e poi cancellata parte come null, non come stringa vuota", async () => {
    // Il campo si può svuotare, e non serve nemmeno volerlo: un Backspace su un
    // segmento di una data completa mette `value` a "" e fa scattare il `change`.
    // Con `??` quella stringa vuota arrivava intera nel corpo, il backend la
    // rifiutava con un 422, e «riprova» rimandava lo stesso corpo per sempre —
    // tutta la sistemazione bloccata, con l'unica uscita in un ricaricamento che
    // butta via ogni risoluzione.
    const user = userEvent.setup();
    const fetchMock = stubRoutedFetch((path) =>
      path.endsWith("/shopping-list/stock") ? [{ created: 2 }, 201] : [CHECKED]
    );
    renderScreen();

    for (const testo of ["yogurt greco", "mele"]) {
      const riga = (await screen.findByText(testo)).closest("li")!;
      await user.click(within(riga).getByRole("button", { name: /sfuso/i }));
    }
    const rigaYogurt = screen.getByText("yogurt greco").closest("li")!;
    await user.click(within(rigaYogurt).getByRole("button", { name: /scadenza/i }));
    const campo = within(rigaYogurt).getByLabelText(/scadenza di yogurt greco/i);
    fireEvent.change(campo, { target: { value: "2026-10-02" } });
    // ci ripensa e svuota
    fireEvent.change(campo, { target: { value: "" } });
    await user.click(screen.getByRole("button", { name: /metti in dispensa/i }));

    await waitFor(() => {
      expect(postBody(fetchMock, "/shopping-list/stock").entries).toEqual([
        expect.objectContaining({ shopping_item_id: "s1", expires_on: null }),
        expect.objectContaining({ shopping_item_id: "s2", expires_on: null }),
      ]);
    });
  });

  it("la data scritta parte con la sistemazione, e le altre righe restano senza", async () => {
    const user = userEvent.setup();
    const spy = vi.fn((url: unknown, _init?: RequestInit) => {
      if (String(url).includes("/stock")) return Promise.resolve(respond({ created: 2 }, 201));
      return Promise.resolve(respond(CHECKED));
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();

    // entrambe le voci hanno già un ingrediente: si confermano sfuse
    for (const testo of ["yogurt greco", "mele"]) {
      const riga = (await screen.findByText(testo)).closest("li")!;
      await user.click(within(riga).getByRole("button", { name: /sfuso/i }));
    }
    const rigaYogurt = screen.getByText("yogurt greco").closest("li")!;
    await user.click(within(rigaYogurt).getByRole("button", { name: /scadenza/i }));
    fireEvent.change(within(rigaYogurt).getByLabelText(/scadenza di yogurt greco/i), {
      target: { value: "2026-10-02" },
    });
    await user.click(screen.getByRole("button", { name: /metti in dispensa/i }));

    await waitFor(() => {
      const stock = spy.mock.calls.find(([url]) => String(url).includes("/stock"));
      expect(JSON.parse(String((stock![1] as RequestInit).body)).entries).toEqual([
        expect.objectContaining({ shopping_item_id: "s1", expires_on: "2026-10-02" }),
        expect.objectContaining({ shopping_item_id: "s2", expires_on: null }),
      ]);
    });
  });
});
