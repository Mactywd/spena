import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { StockingScreen } from "./StockingScreen";
import { UnauthorizedError } from "../../api/client";
import { NoticeProvider } from "../../components/ui/NoticeProvider";

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
  id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco",
  name: "Total 0%", brand: "Fage", barcode: "52010",
  source: "openfoodfacts", nutrients: { kcal: 57 }, image_url: null,
};
// stesso nome, ingrediente diverso: la coppia (ingrediente, prodotto) che il
// backend respinge con 409, e che nessuna delle due strade deve poter costruire
const OTHER_INGREDIENT_PRODUCT = {
  ...FAGE, id: "p2", ingredient_id: "i9", ingredient_name: "cosa strana",
  name: "Total 0% magro",
};

// come in App.tsx: l'avviso unico sta sopra il router, e sopravvive al passaggio in
// Dispensa che segue «Metti in dispensa» (T4)
function renderScreen(client?: QueryClient) {
  const queryClient =
    client ??
    new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
  return render(
    <QueryClientProvider client={queryClient}>
      <NoticeProvider>
        <MemoryRouter initialEntries={["/sistema"]}>
          <Routes>
            <Route path="/sistema" element={<StockingScreen />} />
            <Route path="/dispensa" element={<h1>Dispensa</h1>} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

/** Apre «Abbina» su una voce senza ingrediente — la riga nasce chiusa (spec T3 §4.3) — e
 * torna il campo del selettore, che parte già dal testo della voce. Per ruolo e non per
 * etichetta: l'elenco dei suggerimenti si chiama «Suggerimenti: Abbina un ingrediente
 * per …», e `getByLabelText(/Abbina un ingrediente/)` troverebbe anche lui. */
async function openMatch(rawText = "cosa strana") {
  await userEvent.click(await screen.findByRole("button", { name: `Abbina: ${rawText}` }));
  return screen.getByRole("textbox", { name: `Abbina un ingrediente per ${rawText}` });
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
    const spy = stubRoutedFetch((path) =>
      path.endsWith("/shopping-list/stock") ? [{ created: 1 }, 201] : [CHECKED]
    );

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
    await userEvent.click(screen.getByRole("button", { name: /Metti in dispensa/ }));

    expect(postBody(spy, "/shopping-list/stock").entries).toEqual([
      { shopping_item_id: "s2", ingredient_id: "i2", product_id: null, expires_on: null,
        barcode: null },
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
    // prima la domanda (S20): il sì porta al modulo come prima
    await userEvent.click(await screen.findByRole("button", { name: "Sì" }));

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
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));

    expect(postBody(spy, "/stock").entries).toEqual([
      { shopping_item_id: "s1", ingredient_id: "i1", product_id: "p1", expires_on: null,
        barcode: null },
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
    const note = screen.getByText(/di un altro ingrediente/);
    // e dice quale (spec T3 §4.3): il nome lo manda il server
    expect(note).toHaveTextContent("è di un altro ingrediente: cosa strana");
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
    const note = await screen.findByText(/di un altro ingrediente/);
    // dice quale, e non è un guasto: niente allarme, niente rosso (spec T3 §4.3)
    expect(note).toHaveTextContent("«Total 0% magro» è di un altro ingrediente: cosa strana.");
    expect(note).not.toHaveAttribute("role", "alert");
    expect(note.className).not.toContain("text-danger");
    // la voce non è risolta: le tre strade sono ancora tutte aperte
    expect(screen.getByRole("button", { name: /Sfuso.*yogurt greco/i })).toBeDefined();
    // col pannello aperto «Metti in dispensa» non c'è (decisione 1), e chiuso il
    // pannello è spento: il 409 non è raggiungibile da qui
    expect(screen.queryByRole("button", { name: /Metti in dispensa/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    const stock = screen.getByRole("button", { name: "Metti in dispensa" });
    expect(stock).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(stock);
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
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));
    await vi.waitFor(() =>
      expect(postBody(spy, "/shopping-list/stock").entries).toEqual([
        { shopping_item_id: "s2", ingredient_id: "i2", product_id: null, expires_on: null,
          barcode: null },
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
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));

    const avviso = await screen.findByRole("alert");
    expect(avviso).toHaveTextContent(/non esiste più/);
    expect(avviso).toHaveTextContent(/non ho messo in dispensa niente/i);
    expect(screen.getByRole("button", { name: /Rileggi la spesa/ })).toBeDefined();
  });

  it("un guasto del server nel mettere in dispensa lo dice con «server», non con «backend»", async () => {
    stubRoutedFetch((path) =>
      path.includes("/shopping-list/stock") ? [{ detail: "giù" }, 500] : [CHECKED]
    );

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));

    const avviso = await screen.findByRole("alert");
    expect(avviso).toHaveTextContent(/è il server che non risponde/);
    expect(avviso.textContent).not.toMatch(/backend/);
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
    const spy = vi.fn().mockResolvedValue(respond(CHECKED));
    vi.stubGlobal("fetch", spy);
    renderScreen();
    await screen.findByText("mele");
    // `aria-disabled` e non `disabled`: mentre la sistemazione è in volo il pulsante deve
    // tenere il fuoco. E spento dice perché (dal giro, da non riprogettare via)
    const stock = screen.getByRole("button", { name: "Metti in dispensa" });
    expect(stock).toHaveAttribute("aria-disabled", "true");
    expect(stock.hasAttribute("disabled")).toBe(false);
    // il perché non è solo scritto sotto: è la descrizione del pulsante, e chi ci arriva
    // da tastiera lo sente (`unavailableReason`, Consegna 6a)
    expect(stock).toHaveAccessibleDescription(
      "Scegli come entra almeno una voce: codice, catalogo o sfuso."
    );
    expect(
      screen.getByText("Scegli come entra almeno una voce: codice, catalogo o sfuso.")
    ).toBeDefined();
    await userEvent.click(stock);
    expect(spy.mock.calls.some(([url]) => String(url).endsWith("/shopping-list/stock"))).toBe(
      false
    );
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
    // «non trovato» sarebbe falso: non l'ha cercato nessuno (S20)
    expect(screen.getByText("Non ho potuto cercare il codice: scrivi tu nome e marca."))
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

    // il modulo aperto lascia a video solo la sua voce (decisione 1): si chiude
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
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
    await userEvent.click(await screen.findByRole("button", { name: "Sì" }));
    expect(await screen.findByLabelText("Nome")).toHaveValue("Passata Rustica");

    // il modulo aperto lascia a video solo la sua voce (decisione 1): si chiude
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
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

    // la voce non abbinata è chiusa: «Abbina» apre il selettore (spec T3 §4.3)
    const matchField = await openMatch();
    await userEvent.clear(matchField);
    await userEvent.type(matchField, "strana");

    await userEvent.click(await screen.findByRole("option", { name: /Cosa Strana/i }));
    await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*cosa strana/i }));
    await userEvent.click(screen.getByRole("button", { name: /Metti in dispensa/ }));

    // l'abbinamento fatto a mano deve arrivare davvero nel POST: è il punto di
    // tutto il percorso, ed è esattamente ciò che prima spariva in silenzio
    await vi.waitFor(() =>
      expect(postBody(spy, "/shopping-list/stock").entries).toEqual([
        { shopping_item_id: "s3", ingredient_id: "i9", product_id: null, expires_on: null,
          barcode: null },
      ])
    );
  });

  it("se nessun ingrediente corrisponde lo dice, e lascia crearlo col nome da correggere", async () => {
    // è il caso normale per un testo spaiato: cercare lo stesso testo che non ha
    // trovato niente non troverà niente neanche ora
    const spy = stubRoutedFetch((path, init) => {
      if (path.includes("/ingredients/search")) return [[]];
      if (path.endsWith("/ingredients") && init?.method === "POST") return [STRANGE, 201];
      return [UNMATCHED];
    });

    renderScreen();
    await openMatch();
    // «nessun ingrediente corrisponde» lo dice il selettore unico, offrendo di
    // aggiungerlo (spec T3 §3.5)
    const offer = await screen.findByRole("button", { name: "Aggiungi «cosa strana»" });
    // e la ricerca vuota non propone niente da scegliere
    expect(screen.queryByRole("option")).toBeNull();
    await userEvent.click(offer);
    // il nome parte dal testo della voce, ma è un campo da correggere (dal giro)
    expect(screen.getByLabelText("Come si chiama in generale?")).toHaveValue("cosa strana");
    // non tocca il <select>: è la prova che chi non sceglie niente ottiene
    // esattamente quel che otteneva prima, cioè "altro"
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));

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
    await openMatch();
    await userEvent.click(await screen.findByRole("button", { name: "Aggiungi «cosa strana»" }));

    const reparto = screen.getByLabelText("Reparto");
    // il non alimentare è offerto: è l'unico modo perché un detersivo entri in
    // dispensa senza passare per «altro», che è il reparto delle cose da chiarire
    expect(
      [...(reparto as HTMLSelectElement).options].map((o) => o.value)
    ).toContain("casa");

    await userEvent.selectOptions(reparto, "casa");
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));

    await vi.waitFor(() =>
      expect(postBody(spy, "/ingredients")).toEqual({
        name: "cosa strana",
        display_name: "cosa strana",
        category: "casa",
      })
    );
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
    await openMatch();

    // il suggerimento c'è e resta: la correzione non sta nella ricerca
    expect(await screen.findByRole("option", { name: /Pera/i })).toBeDefined();
    // ...ma non è più lui a decidere se si può creare: l'offerta sta accanto (S6), e
    // una sola — quella del selettore unico, non una seconda accanto al suggerimento
    expect(screen.getAllByRole("button", { name: /^Aggiungi «.*»$/ })).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi «cosa strana»" }));
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "casa");
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));

    await vi.waitFor(() =>
      expect(postBody(spy, "/ingredients")).toEqual({
        name: "cosa strana",
        display_name: "cosa strana",
        category: "casa",
      })
    );
  });

  it("il campo della scadenza non c'è finché non lo si chiede", async () => {
    // dieci campi vuoti a video sono rumore permanente per chi la scadenza non la
    // scrive mai, e questo è già lo schermo più denso dell'app
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(CHECKED)));
    renderScreen();

    await screen.findByText("yogurt greco");
    expect(screen.queryByLabelText(/scadenza/i)).toBeNull();

    await user.click(screen.getByRole("button", { name: "+ scadenza per yogurt greco" }));
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

  // S8: il codice appena letto deve seguire ogni uscita che crea o sceglie un
  // prodotto, così la prossima scansione lo trova. La via diretta (codice ignoto →
  // modulo) lo faceva già; il pannello del catalogo no. Ogni test parte allo stesso
  // modo: un codice che nessuno conosce, il modulo che si apre, e l'utente che lo
  // chiude per passare da un'altra strada.
  describe("il codice letto segue il prodotto (S8)", () => {
    const CODE = "8001234567890";
    const FAGE_SENZA_CODICE = { ...FAGE, barcode: null };

    function stubUnknownCode(search: unknown[] = []) {
      return stubRoutedFetch((path, init) => {
        if (path.includes("/products/barcode/")) {
          return [{ found: false, origin: "unknown", product: null, suggestion: null }];
        }
        if (path.includes("/products/search")) return [search];
        if (path.endsWith("/products") && init?.method === "POST") {
          return [{ ...FAGE_SENZA_CODICE, id: "p9", name: "Greco bianco", barcode: CODE }, 201];
        }
        if (path.includes("/shopping-list/stock")) return [{ created: 1 }, 201];
        return [CHECKED];
      });
    }

    async function readUnknownCodeThenCloseTheForm() {
      await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
      await userEvent.type(screen.getByLabelText("Codice a barre"), `${CODE}{Enter}`);
      await screen.findByRole("heading", { name: /Nuovo prodotto/ });
      await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    }

    it("la creazione a mano dal catalogo porta il codice appena letto", async () => {
      const spy = stubUnknownCode();

      renderScreen();
      await readUnknownCodeThenCloseTheForm();
      await userEvent.click(
        screen.getByRole("button", { name: /Cerca a catalogo.*yogurt greco/i })
      );
      await screen.findByText(/Nessun prodotto con queste parole/);
      await userEvent.click(screen.getByRole("button", { name: "Crea il prodotto a mano" }));
      await userEvent.type(await screen.findByLabelText("Nome"), "Greco bianco");
      await userEvent.click(screen.getByRole("button", { name: "Salva prodotto" }));

      await vi.waitFor(() => expect(postBody(spy, "/products").barcode).toBe(CODE));
    });

    it("un prodotto scelto a catalogo porta il codice appena letto nella sistemazione", async () => {
      const spy = stubUnknownCode([FAGE_SENZA_CODICE]);

      renderScreen();
      await readUnknownCodeThenCloseTheForm();
      await userEvent.click(
        screen.getByRole("button", { name: /Cerca a catalogo.*yogurt greco/i })
      );
      await userEvent.click(await screen.findByRole("option", { name: /Total 0%/ }));
      await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));

      // il client lo manda e basta: se darlo al prodotto è il backend a deciderlo
      // (il prodotto non deve averne un altro, il codice non dev'essere di un altro)
      await vi.waitFor(() =>
        expect(postBody(spy, "/shopping-list/stock").entries).toEqual([
          { shopping_item_id: "s1", ingredient_id: "i1", product_id: "p1", expires_on: null,
            barcode: CODE },
        ])
      );
    });

    it("confermare sfuso dopo un codice ignoto non porta il codice: non c'è un prodotto", async () => {
      const spy = stubUnknownCode();

      renderScreen();
      await readUnknownCodeThenCloseTheForm();
      await userEvent.click(screen.getByRole("button", { name: /Sfuso.*yogurt greco/i }));
      await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));

      await vi.waitFor(() =>
        expect(postBody(spy, "/shopping-list/stock").entries).toEqual([
          { shopping_item_id: "s1", ingredient_id: "i1", product_id: null, expires_on: null,
            barcode: null },
        ])
      );
    });

    it("un codice che è di un prodotto di un altro ingrediente non segue la voce", async () => {
      // quel codice è già preso: portarlo alla creazione a mano darebbe solo un 409
      const spy = stubRoutedFetch((path) => {
        if (path.includes("/products/barcode/")) {
          return [{ found: true, origin: "catalog", suggestion: null,
                    product: OTHER_INGREDIENT_PRODUCT }];
        }
        if (path.includes("/products/search")) return [[FAGE_SENZA_CODICE]];
        if (path.includes("/shopping-list/stock")) return [{ created: 1 }, 201];
        return [CHECKED];
      });

      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
      await userEvent.type(screen.getByLabelText("Codice a barre"), `${CODE}{Enter}`);
      await screen.findByText(/di un altro ingrediente/);
      await userEvent.click(
        screen.getByRole("button", { name: /Cerca a catalogo.*yogurt greco/i })
      );
      await userEvent.click(await screen.findByRole("option", { name: /Total 0%/ }));
      await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));

      await vi.waitFor(() =>
        expect(postBody(spy, "/shopping-list/stock").entries[0].barcode).toBeNull()
      );
    });
  });

  describe("un prodotto di Open Food Facts non entra senza una domanda (S20)", () => {
    // il caso del giro di T3: gli spaghetti letti sulla voce «pomodoro», e un tocco
    // su «Salva» li faceva diventare per sempre un prodotto di pomodoro
    const SPAGHETTI = {
      found: true, origin: "openfoodfacts", product: null, valid_checksum: true,
      suggestion: { name: "Spaghetti n.5", brand: "Barilla", barcode: "8076800195057",
                    nutrients: { kcal: 359 }, image_url: null },
    };

    function stubSpaghetti() {
      return stubRoutedFetch((path, init) => {
        if (path.includes("/products/barcode/")) return [SPAGHETTI];
        if (path.includes("/products/search")) return [[]];
        if (path.endsWith("/products") && init?.method === "POST") return [FAGE, 201];
        return [CHECKED];
      });
    }

    async function readSpaghettiOnYogurt() {
      await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
      await userEvent.type(screen.getByLabelText("Codice a barre"), "8076800195057{Enter}");
    }

    it("chiede se è l'ingrediente della voce, con il nome di Open Food Facts accanto", async () => {
      stubSpaghetti();
      renderScreen();
      await readSpaghettiOnYogurt();

      expect(await screen.findByRole("heading", { name: "È un «yogurt greco»?" })).toBeDefined();
      expect(
        screen.getByText("Su Open Food Facts è «Spaghetti n.5», di Barilla.")
      ).toBeDefined();
      // niente modulo e niente «Salva» finché non si risponde
      expect(screen.queryByRole("heading", { name: /Nuovo prodotto/ })).toBeNull();
      expect(screen.queryByRole("button", { name: "Salva prodotto" })).toBeNull();
    });

    it("«No, è un'altra cosa» riporta ai pulsanti della voce, senza salvare niente", async () => {
      const spy = stubSpaghetti();
      renderScreen();
      await readSpaghettiOnYogurt();

      await userEvent.click(await screen.findByRole("button", { name: "No, è un'altra cosa" }));

      expect(screen.queryByRole("heading", { name: "È un «yogurt greco»?" })).toBeNull();
      expect(screen.queryByRole("heading", { name: /Nuovo prodotto/ })).toBeNull();
      expect(screen.getByRole("button", { name: /Codice.*yogurt greco/i })).toBeDefined();
      expect(screen.getByRole("button", { name: /Sfuso.*yogurt greco/ })).toBeDefined();
      expect(
        spy.mock.calls.some(([url, init]) =>
          String(url).endsWith("/products") && (init as RequestInit)?.method === "POST")
      ).toBe(false);

      // e il codice degli spaghetti non segue la voce: creato a mano dal catalogo,
      // il prodotto dello yogurt non deve portarselo dietro
      await userEvent.click(screen.getByRole("button", { name: /Cerca a catalogo.*yogurt greco/i }));
      await screen.findByText(/Nessun prodotto con queste parole/);
      await userEvent.click(screen.getByRole("button", { name: "Crea il prodotto a mano" }));
      expect(
        await screen.findByText("Nessun codice a barre verrà legato a questo prodotto.")
      ).toBeDefined();
    });

    it("un sì apre il modulo precompilato, che dice da dove vengono i dati", async () => {
      stubSpaghetti();
      renderScreen();
      await readSpaghettiOnYogurt();

      await userEvent.click(await screen.findByRole("button", { name: "Sì" }));

      expect(await screen.findByLabelText("Nome")).toHaveValue("Spaghetti n.5");
      expect(
        screen.getByText("Trovato su Open Food Facts: controlla i dati prima di salvare.")
      ).toBeDefined();
      expect(screen.getByText("Il codice 8076800195057 verrà legato a questo prodotto."))
        .toBeDefined();
    });

    it("anche senza nome su Open Food Facts la domanda si fa, e il nome parte vuoto", async () => {
      stubRoutedFetch((path) =>
        path.includes("/products/barcode/")
          ? [{ ...SPAGHETTI, suggestion: { ...SPAGHETTI.suggestion, name: null, brand: null } }]
          : [CHECKED]
      );
      renderScreen();
      await readSpaghettiOnYogurt();

      expect(await screen.findByText("Su Open Food Facts è senza nome.")).toBeDefined();
      await userEvent.click(screen.getByRole("button", { name: "Sì" }));
      expect(await screen.findByLabelText("Nome")).toHaveValue("");
      expect(screen.getByRole("button", { name: "Salva prodotto" })).toBeDisabled();
    });

    it("un codice che Open Food Facts non conosce apre il modulo e lo dice", async () => {
      stubRoutedFetch((path) =>
        path.includes("/products/barcode/")
          ? [{ found: false, origin: "unknown", product: null, suggestion: null,
               valid_checksum: true }]
          : [CHECKED]
      );
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
      await userEvent.type(screen.getByLabelText("Codice a barre"), "8001120000002{Enter}");

      // nessuna domanda: non c'è niente di Open Food Facts da confrontare
      expect(await screen.findByRole("heading", { name: /Nuovo prodotto/ })).toBeDefined();
      expect(screen.getByText("Non trovato su Open Food Facts: scrivi tu nome e marca."))
        .toBeDefined();
      expect(screen.getByText("Il codice 8001120000002 verrà legato a questo prodotto."))
        .toBeDefined();
    });

    describe("la cifra di controllo", () => {
      const BAD = { found: false, origin: "unknown", product: null, suggestion: null,
                    valid_checksum: false };
      const GOOD = { ...BAD, valid_checksum: true };

      it("un codice che non torna lo dice, lascia correggerlo, e lascia andare avanti", async () => {
        stubRoutedFetch((path) => {
          if (path.endsWith("/products/barcode/1234")) return [BAD];
          if (path.includes("/products/barcode/")) return [GOOD];
          return [CHECKED];
        });
        renderScreen();
        await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
        const field = screen.getByLabelText("Codice a barre");
        await userEvent.type(field, "1234{Enter}");

        expect(await screen.findByText("Questo codice non torna: ricontrollalo.")).toBeDefined();
        expect(screen.queryByRole("heading", { name: /Nuovo prodotto/ })).toBeNull();
        // il codice resta lì, correggibile
        expect(field).toHaveValue("1234");

        // corretto, riparte da capo
        await userEvent.clear(field);
        await userEvent.type(field, "8001120000002{Enter}");
        expect(await screen.findByRole("heading", { name: /Nuovo prodotto/ })).toBeDefined();
        expect(screen.queryByText("Questo codice non torna: ricontrollalo.")).toBeNull();
      });

      it("chi ha la confezione in mano può usarlo lo stesso: i codici di negozio esistono", async () => {
        stubRoutedFetch((path) =>
          path.includes("/products/barcode/") ? [BAD] : [CHECKED]
        );
        renderScreen();
        await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
        await userEvent.type(screen.getByLabelText("Codice a barre"), "1234{Enter}");

        await userEvent.click(
          await screen.findByRole("button", { name: "Usa questo codice lo stesso" })
        );

        expect(await screen.findByRole("heading", { name: /Nuovo prodotto/ })).toBeDefined();
        expect(screen.getByText("Il codice 1234 verrà legato a questo prodotto.")).toBeDefined();
      });

      it("un codice già nel nostro catalogo si aggancia anche se non torna", async () => {
        // se è in catalogo qualcuno l'ha già confermato con la confezione in mano
        stubRoutedFetch((path) =>
          path.includes("/products/barcode/")
            ? [{ found: true, origin: "catalog", suggestion: null, product: FAGE,
                 valid_checksum: false }]
            : [CHECKED]
        );
        renderScreen();
        await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
        await userEvent.type(screen.getByLabelText("Codice a barre"), "52010{Enter}");

        expect(await screen.findByText("Total 0%")).toBeDefined();
        expect(screen.queryByText("Questo codice non torna: ricontrollalo.")).toBeNull();
      });
    });
  });

  describe("l'abbinamento resta sulla voce (S19)", () => {
    function patchCalls(spy: ReturnType<typeof stubRoutedFetch>) {
      return spy.mock.calls
        .filter(([, init]) => (init as RequestInit)?.method === "PATCH")
        .map(([url, init]) => [String(url), JSON.parse(String((init as RequestInit).body))]);
    }

    function listReads(spy: ReturnType<typeof stubRoutedFetch>) {
      return spy.mock.calls.filter(
        ([url, init]) => String(url).includes("/shopping-list?") && !(init as RequestInit)?.method
      ).length;
    }

    it("l'ingrediente scelto si scrive subito sulla voce, e la lista si rilegge", async () => {
      const spy = stubRoutedFetch((path, init) => {
        if (path.includes("/ingredients/search")) return [[STRANGE]];
        if (init?.method === "PATCH") return [{ ...UNMATCHED[0], ingredient_id: "i9" }];
        return [UNMATCHED];
      });

      renderScreen();
      const field = await openMatch();
      await userEvent.clear(field);
      await userEvent.type(field, "strana");
      const readsBefore = listReads(spy);
      await userEvent.click(await screen.findByRole("option", { name: /Cosa Strana/i }));

      await vi.waitFor(() =>
        expect(patchCalls(spy)).toEqual([
          ["/api/v1/shopping-list/s3", { ingredient_id: "i9" }],
        ])
      );
      // la lista in cache non dice ancora il reparto giusto: si rilegge
      await vi.waitFor(() => expect(listReads(spy)).toBeGreaterThan(readsBefore));
      // senza aspettare la spesa di oggi
      expect(
        spy.mock.calls.some(([url]) => String(url).endsWith("/shopping-list/stock"))
      ).toBe(false);
    });

    it("dopo l'abbinamento il fuoco resta sulla prima icona, anche quando la voce passa nel suo reparto", async () => {
      // la rilettura dopo la PATCH dà alla voce il suo reparto: la riga lascia «Senza
      // reparto» e rinasce in un'altra sezione, e il fuoco non deve cadere sulla pagina
      // (decisione 18)
      let patched = false;
      stubRoutedFetch((path, init) => {
        if (path.includes("/ingredients/search")) return [[STRANGE]];
        if (init?.method === "PATCH") {
          patched = true;
          return [{ ...UNMATCHED[0], ingredient_id: "i9" }];
        }
        return [
          patched
            ? [{ ...UNMATCHED[0], ingredient_id: "i9", ingredient_name: "cosa strana",
                 ingredient_category: "altro" }]
            : UNMATCHED,
        ];
      });

      renderScreen();
      const field = await openMatch();
      await userEvent.clear(field);
      await userEvent.type(field, "strana");
      await userEvent.click(await screen.findByRole("option", { name: /Cosa Strana/i }));

      expect(await screen.findByRole("heading", { level: 2, name: "Altro" })).toBeDefined();
      expect(screen.queryByRole("heading", { name: "Senza reparto" })).toBeNull();
      await vi.waitFor(() =>
        expect(document.activeElement).toBe(
          screen.getByRole("button", { name: "Codice a barre per cosa strana" })
        )
      );
    });

    it("il fuoco chiesto da un pannello chiuso su un'altra voce vince su quello dell'abbinamento in attesa", async () => {
      // La voce abbinata aspetta la rilettura per riprendere il fuoco; intanto si apre e
      // si chiude un pannello sulle mele. Tornata la vista intera, «cosa strana» — ora in
      // «Altro», prima di «Frutta» — rinasce prima delle mele: se la sua richiesta
      // vecchia scattasse, il fuoco di «Annulla» finirebbe su di lei.
      let answerPatch: (response: Response) => void = () => {};
      let patched = false;
      vi.stubGlobal(
        "fetch",
        vi.fn((url: unknown, init?: RequestInit) => {
          const path = String(url);
          if (init?.method === "PATCH") {
            return new Promise<Response>((resolve) => {
              answerPatch = (response) => {
                patched = true;
                resolve(response);
              };
            });
          }
          if (path.includes("/ingredients/search")) return Promise.resolve(respond([STRANGE]));
          if (path.includes("/products/search")) return Promise.resolve(respond([]));
          return Promise.resolve(
            respond([
              patched
                ? { ...UNMATCHED[0], ingredient_id: "i9", ingredient_name: "cosa strana",
                    ingredient_category: "altro" }
                : UNMATCHED[0],
              CHECKED[1],
            ])
          );
        })
      );

      renderScreen();
      const field = await openMatch();
      await userEvent.clear(field);
      await userEvent.type(field, "strana");
      await userEvent.click(await screen.findByRole("option", { name: /Cosa Strana/i }));
      await userEvent.click(screen.getByRole("button", { name: "Cerca a catalogo per mele" }));
      expect(screen.queryByText("cosa strana")).toBeNull();

      await act(async () =>
        answerPatch(respond({ ...UNMATCHED[0], ingredient_id: "i9" }))
      );
      await userEvent.click(screen.getByRole("button", { name: "Annulla" }));

      expect(await screen.findByRole("heading", { level: 2, name: "Altro" })).toBeDefined();
      expect(document.activeElement).toBe(
        screen.getByRole("button", { name: "Cerca a catalogo per mele" })
      );
    });

    it("se la voce non si aggiorna lo dice accanto, e la voce si sistema lo stesso", async () => {
      stubRoutedFetch((path, init) => {
        if (path.includes("/ingredients/search")) return [[STRANGE]];
        if (init?.method === "PATCH") return [{ detail: "giù" }, 500];
        return [UNMATCHED];
      });

      renderScreen();
      const field = await openMatch();
      await userEvent.clear(field);
      await userEvent.type(field, "strana");
      await userEvent.click(await screen.findByRole("option", { name: /Cosa Strana/i }));

      expect(
        await screen.findByText(
          "Non sono riuscito a ricordare l'abbinamento in lista: la voce si sistema lo " +
            "stesso, ma se oggi non la metti in dispensa andrà rifatto."
        )
      ).toBeDefined();
      expect(screen.getByRole("button", { name: /Sfuso.*cosa strana/i })).toBeDefined();
      expect(screen.getByRole("button", { name: /Riprova.*cosa strana/i })).toBeDefined();
    });

    it("creare un ingrediente che c'è già aggancia quello, invece di dare errore", async () => {
      const spy = stubRoutedFetch((path, init) => {
        if (path.includes("/ingredients/search")) return [[]];
        if (path.endsWith("/ingredients") && init?.method === "POST") {
          return [{ detail: "ingrediente già presente", existing: STRANGE }, 409];
        }
        if (init?.method === "PATCH") return [{ ...UNMATCHED[0], ingredient_id: "i9" }];
        return [UNMATCHED];
      });

      renderScreen();
      await openMatch();
      await userEvent.click(await screen.findByRole("button", { name: "Aggiungi «cosa strana»" }));
      await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));

      expect(await screen.findByRole("button", { name: /Sfuso.*cosa strana/i })).toBeDefined();
      expect(screen.queryByText(/Non sono riuscito a creare l'ingrediente/)).toBeNull();
      await vi.waitFor(() =>
        expect(patchCalls(spy)).toEqual([
          ["/api/v1/shopping-list/s3", { ingredient_id: "i9" }],
        ])
      );
    });

    it("gli altri fallimenti della creazione tengono il loro messaggio", async () => {
      stubRoutedFetch((path, init) => {
        if (path.includes("/ingredients/search")) return [[]];
        if (path.endsWith("/ingredients") && init?.method === "POST") {
          return [{ detail: "giù" }, 500];
        }
        return [UNMATCHED];
      });

      renderScreen();
      await openMatch();
      await userEvent.click(await screen.findByRole("button", { name: "Aggiungi «cosa strana»" }));
      await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));

      expect(await screen.findByText(/Non sono riuscito a creare l'ingrediente/)).toBeDefined();
      expect(screen.queryByRole("button", { name: /Sfuso.*cosa strana/i })).toBeNull();
    });
  });

  describe("la vista (T3 Consegna 3)", () => {
    it("una sezione per reparto, nell'ordine della lista; le voci senza ingrediente in fondo", async () => {
      stubRoutedFetch(() => [[...UNMATCHED, ...CHECKED]]);
      renderScreen();
      await screen.findByText("mele");
      expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
        "Frutta",
        "Latticini",
        "Senza reparto",
      ]);
    });

    it("un pannello aperto lascia a video solo la sua voce, e chiuderlo rimette tutto com'era", async () => {
      stubRoutedFetch((path) =>
        path.includes("/search") ? [[]] : [[...CHECKED, ...UNMATCHED]]
      );
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*yogurt greco/i }));
      await userEvent.click(screen.getByRole("button", { name: "Cerca a catalogo per mele" }));

      // il titolo del pannello sta subito sotto quello della pagina: h1 → h2
      expect(
        screen.getByRole("heading", { level: 2, name: "Cerca a catalogo per «mele»" })
      ).toBeDefined();
      // le altre voci, i reparti e «Metti in dispensa» non ci sono (decisione 1, Mattia)
      expect(screen.queryByText("yogurt greco")).toBeNull();
      expect(screen.queryByText("cosa strana")).toBeNull();
      for (const reparto of ["Frutta", "Latticini", "Senza reparto"]) {
        expect(screen.queryByRole("heading", { name: reparto })).toBeNull();
      }
      expect(screen.queryByRole("button", { name: /Metti in dispensa/ })).toBeNull();
      // il fuoco resta sul pulsante che l'ha aperto, non cade sulla pagina
      expect(document.activeElement).toBe(
        screen.getByRole("button", { name: "Cerca a catalogo per mele" })
      );

      await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
      // tutto com'era, e la scelta fatta prima resta
      const yogurt = screen.getByText("yogurt greco").closest("li")!;
      expect(within(yogurt).getByText("Sfuso")).toBeDefined();
      expect(screen.getByText("cosa strana")).toBeDefined();
      expect(screen.getByRole("button", { name: "Metti in dispensa 1" })).toBeDefined();
      expect(document.activeElement).toBe(
        screen.getByRole("button", { name: "Cerca a catalogo per mele" })
      );

      // «Abbina» il fuoco lo prende da sé, ma annullando torna al suo pulsante
      await openMatch();
      await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
      expect(document.activeElement).toBe(
        screen.getByRole("button", { name: "Abbina: cosa strana" })
      );
    });

    it("un campo della scadenza aperto non ruba il fuoco quando la sua riga rinasce", async () => {
      // Dall'e2e (Task 8): la riga rinasce aprendo e chiudendo un pannello, e un campo
      // della scadenza con `autoFocus` si riprendeva il fuoco a ogni rinascita — il
      // fuoco di «Annulla» finiva nella data di un'altra voce invece che sul pulsante
      // che aveva aperto il pannello (decisione 1)
      stubRoutedFetch((path) => (path.includes("/products/search") ? [[]] : [CHECKED]));
      renderScreen();
      await userEvent.click(
        await screen.findByRole("button", { name: "+ scadenza per yogurt greco" })
      );
      // chiesto con un tocco, il campo prende il fuoco
      expect(document.activeElement).toBe(screen.getByLabelText("Scadenza di yogurt greco"));

      // su un'altra voce: chiudendo, lo yogurt torna col suo campo, e il fuoco no
      const meleCatalogo = () => screen.getByRole("button", { name: "Cerca a catalogo per mele" });
      await userEvent.click(meleCatalogo());
      await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
      expect(screen.getByLabelText("Scadenza di yogurt greco")).toBeDefined();
      expect(document.activeElement).toBe(meleCatalogo());

      // sulla stessa voce: il campo resta aperto sotto il pannello, il fuoco sul pulsante
      const yogurtCatalogo = () =>
        screen.getByRole("button", { name: "Cerca a catalogo per yogurt greco" });
      await userEvent.click(yogurtCatalogo());
      expect(document.activeElement).toBe(yogurtCatalogo());
      await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
      expect(document.activeElement).toBe(yogurtCatalogo());
    });

    it("un pannello alla volta: aprirne un altro sulla stessa voce chiude il primo", async () => {
      stubRoutedFetch((path) => (path.includes("/products/search") ? [[]] : [CHECKED]));
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: "Codice a barre per mele" }));
      expect(screen.getByRole("heading", { name: "Codice a barre per «mele»" })).toBeDefined();
      await userEvent.click(screen.getByRole("button", { name: "Cerca a catalogo per mele" }));
      expect(screen.getByRole("heading", { name: "Cerca a catalogo per «mele»" })).toBeDefined();
      expect(screen.queryByRole("heading", { name: "Codice a barre per «mele»" })).toBeNull();
      expect(screen.queryByLabelText("Codice a barre")).toBeNull();
    });

    it("un codice che risponde dopo «Annulla» non sceglie niente, e non chiude il pannello di un'altra voce", async () => {
      // react-query chiama gli `on…` di una mutazione anche a pannello smontato: il
      // lookup partito sotto lo yogurt risponde quando davanti c'è già un'altra voce
      let answer: (response: Response) => void = () => {};
      vi.stubGlobal(
        "fetch",
        vi.fn((url: unknown) => {
          if (String(url).includes("/products/barcode/")) {
            return new Promise<Response>((resolve) => {
              answer = resolve;
            });
          }
          if (String(url).includes("/products/search")) return Promise.resolve(respond([]));
          return Promise.resolve(respond(CHECKED));
        })
      );
      renderScreen();
      await userEvent.click(
        await screen.findByRole("button", { name: "Codice a barre per yogurt greco" })
      );
      await userEvent.type(screen.getByLabelText("Codice a barre"), "52010{Enter}");
      await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
      await userEvent.click(screen.getByRole("button", { name: "Cerca a catalogo per mele" }));

      await act(async () => {
        answer(respond({ found: true, origin: "catalog", suggestion: null, product: FAGE }));
        await new Promise((resolve) => setTimeout(resolve, 50));
      });

      // il catalogo delle mele resta aperto
      expect(screen.getByRole("heading", { name: "Cerca a catalogo per «mele»" })).toBeDefined();
      await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
      // e lo yogurt non ha preso il prodotto che nessuno ha più scelto
      expect(screen.queryByText("Total 0%")).toBeNull();
      expect(screen.getByRole("button", { name: /Sfuso.*yogurt greco/i })).toBeDefined();
      expect(screen.getByRole("button", { name: "Metti in dispensa" })).toHaveAttribute(
        "aria-disabled",
        "true"
      );
    });

    it("il pannello porta in cima la sua voce (S10)", async () => {
      const targets: Element[] = [];
      const reveal = vi
        .spyOn(Element.prototype, "scrollIntoView")
        .mockImplementation(function (this: Element) {
          targets.push(this);
        });
      stubRoutedFetch(() => [CHECKED]);
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: "Codice a barre per mele" }));
      expect(targets.at(-1)).toBe(screen.getByText("mele").closest("li"));
      reveal.mockRestore();
    });

    it("niente da sistemare: lo dice, e porta alla Lista, senza pulsanti spenti", async () => {
      stubRoutedFetch(() => [[]]);
      renderScreen();
      expect(await screen.findByRole("heading", { name: "Niente da sistemare" })).toBeDefined();
      expect(screen.getByRole("link", { name: "Vai alla Lista" }).getAttribute("href")).toBe("/lista");
      expect(screen.queryByRole("button", { name: /Metti in dispensa/ })).toBeNull();
    });
  });

  describe("«Metti in dispensa» dice quante, e l'avviso arriva in Dispensa (T4)", () => {
    function stubStock() {
      return stubRoutedFetch((path) =>
        path.endsWith("/shopping-list/stock") ? [{ created: 1 }, 201] : [[...CHECKED, ...UNMATCHED]]
      );
    }

    it("il numero sul pulsante è quello delle voci che partono", async () => {
      const spy = stubStock();
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
      await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));
      await vi.waitFor(() =>
        expect(postBody(spy, "/shopping-list/stock").entries).toHaveLength(1)
      );
    });

    it("in Dispensa, quante sono entrate e quante restano in lista", async () => {
      stubStock();
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
      await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));
      expect(await screen.findByRole("heading", { name: "Dispensa" })).toBeDefined();
      // le due non mandate — lo yogurt senza scelta, la voce senza ingrediente — restano
      // spuntate in lista; le voci ancora da comprare non contano (decisione 4)
      expect(screen.getByText("1 in dispensa · 2 restano in lista")).toBeDefined();
    });

    it("se sono entrate tutte, l'avviso non parla della lista", async () => {
      stubRoutedFetch((path) =>
        path.endsWith("/shopping-list/stock") ? [{ created: 2 }, 201] : [CHECKED]
      );
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*yogurt greco/i }));
      await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
      await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 2" }));
      expect(await screen.findByText("2 in dispensa")).toBeDefined();
      expect(screen.queryByText(/in lista/)).toBeNull();
    });
  });
});
