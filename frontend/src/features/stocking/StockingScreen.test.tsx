import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
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
      { shopping_item_id: "s2", ingredient_id: "i2", product_id: null },
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
        { shopping_item_id: "s3", ingredient_id: "i9", product_id: null },
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
        "Nessun ingrediente corrisponde. Puoi crearlo adesso: finisce nel reparto «altro» e la " +
          "voce diventa sistemabile."
      )
    ).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: /Crea l'ingrediente/i }));

    expect(await screen.findByRole("button", { name: /Sfuso.*cosa strana/i })).toBeDefined();
    expect(postBody(spy, "/ingredients")).toEqual({
      name: "cosa strana",
      display_name: "cosa strana",
      category: "altro",
    });
  });
});
