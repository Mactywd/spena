import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { PantryScreen } from "./PantryScreen";

const ITEMS = [
  { id: "p1", ingredient_id: "i1", product_id: "pr1", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", ingredient_kind: "food", product_name: "Total 0%", product_brand: "Fage",
    status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z",
    expires_on: null, expiry: null },
  { id: "p2", ingredient_id: "i1", product_id: "pr2", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", ingredient_kind: "food", product_name: "Pesca", product_brand: "Carrefour",
    status: "low", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z",
    expires_on: null, expiry: null },
  { id: "p3", ingredient_id: "i2", product_id: null, ingredient_name: "mela",
    ingredient_category: "frutta", ingredient_kind: "food", product_name: null, product_brand: null,
    status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z",
    expires_on: "2026-09-28", expiry: "soon" },
];

const MELA = { id: "i2", name: "mela", display_name: "Mela", category: "frutta" };

// S14: una cosa di casa, accanto al cibo di ITEMS
const DETERSIVO = {
  id: "p4", ingredient_id: "i4", product_id: null, ingredient_name: "detersivo per i piatti",
  ingredient_category: "casa", ingredient_kind: "non_food", product_name: null, product_brand: null,
  status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z",
  expires_on: null, expiry: null,
};
const DUE_MONDI = [...ITEMS, DETERSIVO];

// il mondo scelto si ricorda nella sessionStorage (S14): ogni test parte e finisce senza
beforeEach(() => {
  sessionStorage.clear();
});
afterEach(() => {
  sessionStorage.clear();
});

function mondo(nome: "Tutto" | "Cibo" | "Casa") {
  return within(screen.getByRole("group", { name: "Cosa mostrare" })).getByRole("button", { name: nome });
}

/** Un fetch che risponde in base al percorso: l'ingresso diretto ne attraversa tre
 * (la dispensa, la ricerca in anagrafica, la scrittura), e ogni chiamata deve
 * ricevere una Response nuova perché il corpo si legge una volta sola. */
function stubRoutedFetch(route: (path: string, init?: RequestInit) => [unknown, number]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

// senza `NoticeProvider` l'avviso di conferma (la X, il rientro in lista) non
// avrebbe dove comparire: `useNotice()` restituirebbe il no-op del contesto vuoto
function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <NoticeProvider>
          <PantryScreen />
        </NoticeProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("PantryScreen", () => {
  it("per gli sfusi mostra il nome dell'ingrediente", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(ITEMS), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("Mela")).toBeDefined();
  });

  it("elenca separatamente due prodotti dello stesso ingrediente", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(ITEMS), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("Total 0%")).toBeDefined();
    expect(screen.getByText("Pesca")).toBeDefined();
  });

  it("una modifica rifiutata lo dice, accanto alla voce giusta", async () => {
    const spy = vi.fn().mockImplementation((_url: string, init?: RequestInit) =>
      init?.method === "PATCH"
        ? Promise.resolve(new Response(JSON.stringify({ detail: "no" }), { status: 500 }))
        : Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    const row = (await screen.findByText("Total 0%")).closest("li")!;
    fireEvent.click(within(row).getByRole("radio", { name: "Quasi finito" }));

    expect(await within(row).findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
    const other = screen.getByText("Pesca").closest("li")!;
    expect(within(other).queryByRole("alert")).toBeNull();
  });

  it("mentre una modifica è in volo i controlli di quella voce sono bloccati", async () => {
    // due tocchi sulla stessa voce arrivano in ordine ignoto e l'ultimo a rispondere
    // vince: il secondo non deve nemmeno poter partire
    const spy = vi.fn().mockImplementation((_url: string, init?: RequestInit) =>
      init?.method === "PATCH"
        ? new Promise<Response>(() => {})
        : Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    const row = (await screen.findByText("Total 0%")).closest("li")!;
    fireEvent.click(within(row).getByRole("radio", { name: "Quasi finito" }));

    // le tacche sono spente con `aria-disabled`, che tiene il fuoco (StockGauge)
    await waitFor(() =>
      expect(within(row).getByRole("radio", { name: "Disponibile" })).toHaveAttribute("aria-disabled", "true")
    );
    expect(within(row).getByRole("button", { name: "Togli Total 0% dalla dispensa" })).toHaveAttribute("aria-disabled", "true");
    // e un secondo tocco durante il volo non parte, né dalla tacca né dalla ✕ (Button, `busy`).
    // `await act` dopo ogni tocco: `mutate` chiama `mutationFn` solo dopo `onMutate` (TanStack
    // Query 5), quindi senza aspettare il microtask l'asserzione sotto passerebbe anche con
    // la guardia disattivata — non avrebbe ancora visto la seconda `fetch`.
    fireEvent.click(within(row).getByRole("radio", { name: "Finito" }));
    await act(async () => {});
    fireEvent.click(within(row).getByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    await act(async () => {});
    expect(spy.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
    const other = screen.getByText("Pesca").closest("li")!;
    expect(within(other).getByRole("radio", { name: "Disponibile" })).not.toHaveAttribute("aria-disabled");
  });

  it("scrivere nella barra filtra le righe, anche per prodotto e marca", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "fage" } });
    expect(screen.getByText("Total 0%")).toBeDefined();
    expect(screen.queryByText("Pesca")).toBeNull();
    expect(screen.queryByRole("link", { name: "Mela" })).toBeNull();
  });

  it("un testo che non trova niente offre di aggiungerlo", async () => {
    stubRoutedFetch((path) =>
      path.includes("/shopping-list") ? [[], 200] : path.includes("/ingredients") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "sale" } });
    expect(screen.getByText("Niente in dispensa per «sale»")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi «sale»" }));
    expect(screen.getByLabelText("Ingrediente da mettere in dispensa")).toHaveProperty("value", "sale");
    // l'anagrafica non ha «sale»: la Dispensa lo crea lì (S3), e non rimanda più alla lista
    expect(await screen.findByRole("button", { name: "Aggiungi «sale»" })).toBeDefined();
    expect(screen.queryByRole("link", { name: "lista" })).toBeNull();
  });

  it("il + apre l'aggiunta con il testo della barra, e scegliere mette in dispensa", async () => {
    const created = { ...ITEMS[2], id: "p9" };
    // dopo la POST, la dispensa che il refetch legge contiene anche la voce nuova:
    // senza, `revealId` non troverebbe mai la riga "p9" e il porta-in-vista non
    // scatterebbe mai — il test non proverebbe niente sull'aggancio
    let added = false;
    const fetchSpy = stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (path.includes("/ingredients")) return [[MELA], 200];
      if (init?.method === "POST") {
        added = true;
        return [created, 201];
      }
      return [added ? [...ITEMS, created] : ITEMS, 200];
    });
    // uno spy e non un'assegnazione diretta: quella sovrascriverebbe per il resto del
    // file il no-op che `vitest.setup.ts` mette su `Element.prototype`, e nessuna riga
    // qui sotto lo rimetterebbe a posto
    const scrollSpy = vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(() => {});
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mel" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(await screen.findByRole("option", { name: "Mela" }));
    // la scheda di conferma (S3): un tocco in più, e lì si scrive la scadenza
    fireEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    expect(await screen.findByText("In dispensa: Mela")).toBeDefined();
    const post = fetchSpy.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      ingredient_id: "i2", product_id: null, status: "available", expires_on: null, barcode: null,
    });
    // l'aggiunta si chiude e la barra torna vuota
    expect(screen.queryByLabelText("Ingrediente da mettere in dispensa")).toBeNull();
    expect(screen.queryByRole("button", { name: "Metti in dispensa" })).toBeNull();
    expect(screen.getByLabelText("Cerca o aggiungi in dispensa")).toHaveProperty("value", "");
    // la riga nuova arriva e va in vista una volta sola: `onRevealed` spegne `revealId`
    // subito dopo, e un secondo giro non deve richiamare lo scorrimento
    await waitFor(() => expect(scrollSpy).toHaveBeenCalledTimes(1));
    scrollSpy.mockRestore();
  });

  it("chiudere l'aggiunta dopo un fallimento non lo riporta nella prossima", async () => {
    stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (path.includes("/ingredients")) return [[MELA], 200];
      if (init?.method === "POST") return [{ detail: "no" }, 500];
      return [ITEMS, 200];
    });
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mel" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(await screen.findByRole("option", { name: "Mela" }));
    fireEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    expect(await screen.findByText("Non sono riuscito ad aggiungere la voce in dispensa. Riprova.")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Chiudi l'aggiunta" }));

    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "pane" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    expect(
      screen.queryByText("Non sono riuscito ad aggiungere la voce in dispensa. Riprova.")
    ).toBeNull();
  });

  it("un'aggiunta rifiutata lo dice nella scheda dell'aggiunta, che resta aperta", async () => {
    stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (path.includes("/ingredients")) return [[MELA], 200];
      if (init?.method === "POST") return [{ detail: "no" }, 500];
      return [ITEMS, 200];
    });
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mel" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(await screen.findByRole("option", { name: "Mela" }));
    fireEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    expect(await screen.findByText("Non sono riuscito ad aggiungere la voce in dispensa. Riprova.")).toBeDefined();
    expect(screen.getByRole("button", { name: "Metti in dispensa" })).toBeDefined();
  });

  it("il nome del campo dell'aggiunta è quello che si legge (WCAG 2.5.3)", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    // chi usa la voce dice quel che vede: la scritta e il nome accessibile coincidono
    expect(screen.getByText("Ingrediente da mettere in dispensa")).toBeDefined();
    expect(screen.queryByText("Quale ingrediente?")).toBeNull();
  });

  it("la ✕ dell'aggiunta la chiude", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(screen.getByRole("button", { name: "Chiudi l'aggiunta" }));
    expect(screen.queryByLabelText("Ingrediente da mettere in dispensa")).toBeNull();
  });

  it("il riepilogo conta le voci in scadenza e, toccato, mostra solo quelle", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    const summary = await screen.findByRole("button", { name: "1 in scadenza questa settimana" });
    expect(summary.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(summary);
    expect(summary.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("link", { name: "Mela" })).toBeDefined();
    expect(screen.queryByText("Total 0%")).toBeNull();
    fireEvent.click(summary);
    expect(screen.getByText("Total 0%")).toBeDefined();
  });

  it("dal riepilogo premuto, segnare «Finito» lascia la voce in vista con il suo «In lista»", async () => {
    // due voci in scadenza: finita la mela, il riepilogo resta (conta ancora lo
    // yogurt) e con lui il filtro — è lì che la mela spariva insieme al suo «In lista»
    let rows = [{ ...ITEMS[0], expires_on: "2026-09-29", expiry: "soon" }, ITEMS[1], ITEMS[2]];
    stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (init?.method === "PATCH") {
        const { status } = JSON.parse(String(init.body));
        rows = rows.map((row) => (path.includes(`/pantry/${row.id}`) ? { ...row, status } : row));
        return [rows.find((row) => path.includes(`/pantry/${row.id}`)), 200];
      }
      return [rows, 200];
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "2 in scadenza questa settimana" }));
    const gauge = screen.getByRole("radiogroup", { name: "Quanto resta di mela" });
    fireEvent.click(within(gauge).getByRole("radio", { name: "Finito" }));

    const summary = await screen.findByRole("button", { name: "1 in scadenza questa settimana" });
    expect(summary.getAttribute("aria-pressed")).toBe("true");
    const row = screen.getByRole("link", { name: "Mela" }).closest("li")!;
    expect(within(row).getByRole("button", { name: "In lista" })).toBeDefined();
  });

  it("dal riepilogo premuto, un testo che trova solo voci non in scadenza lo dice e offre di mostrare tutto", async () => {
    // «Niente in dispensa per «fage»» sarebbe falso (lo yogurt c'è), e «Aggiungi
    // «fage»» ne creerebbe un doppione
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    const summary = await screen.findByRole("button", { name: "1 in scadenza questa settimana" });
    fireEvent.click(summary);
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "fage" } });
    expect(screen.getByRole("heading", { name: "Niente in scadenza per «fage»" })).toBeDefined();
    expect(screen.queryByRole("heading", { name: /Niente in dispensa/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Aggiungi «fage»" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Mostra tutto" }));
    expect(summary.getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByText("Total 0%")).toBeDefined();
  });

  it("con l'aggiunta aperta, il vuoto non offre un secondo «Aggiungi»", async () => {
    stubRoutedFetch((path) =>
      path.includes("/shopping-list") ? [[], 200] : path.includes("/ingredients") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "sale" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi «sale»" }));
    expect(screen.getByLabelText("Ingrediente da mettere in dispensa")).toBeDefined();
    // subito, prima dell'attesa della ricerca: il vuoto non offre il suo «Aggiungi»
    expect(screen.queryByRole("button", { name: "Aggiungi «sale»" })).toBeNull();
    // dopo l'attesa della ricerca (180 ms) l'anagrafica non ha «sale» e il pannello offre
    // di crearlo (S3): quel «Aggiungi «sale»» è il suo, e il vuoto non ne offre un secondo
    await screen.findByRole("button", { name: "Aggiungi «sale»" });
    expect(screen.getAllByRole("button", { name: "Aggiungi «sale»" })).toHaveLength(1);
  });

  it("un riepilogo che sparisce e poi torna, torna non premuto", async () => {
    let archived = false;
    stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (init?.method === "PATCH") {
        archived = JSON.parse(String(init.body)).archived;
        return [ITEMS[2], 200];
      }
      return [archived ? ITEMS.slice(0, 2) : ITEMS, 200];
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "1 in scadenza questa settimana" }));
    fireEvent.click(screen.getByRole("button", { name: "Togli mela dalla dispensa" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: /in scadenza/ })).toBeNull());
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    const summary = await screen.findByRole("button", { name: "1 in scadenza questa settimana" });
    expect(summary.getAttribute("aria-pressed")).toBe("false");
  });

  it("senza scadenze vicine il riepilogo non c'è", async () => {
    const quiet = ITEMS.map((item) => ({ ...item, expires_on: null, expiry: null }));
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [quiet, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    expect(screen.queryByRole("button", { name: /in scadenza/ })).toBeNull();
  });

  it("una sezione per reparto, con il conteggio, e le finite in fondo", async () => {
    const rows = [
      { ...ITEMS[0], status: "finished" },
      ITEMS[1],
      ITEMS[2],
    ];
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [rows, 200]));
    renderScreen();
    const latticini = await screen.findByRole("region", { name: "Latticini" });
    const links = within(latticini).getAllByRole("link").map((link) => link.getAttribute("href"));
    // Pesca (pr2) prima di Total 0% (pr1), che è finito
    expect(links[0]).toContain("pr2");
    expect(links[1]).toContain("pr1");
    expect(within(latticini).getByText("2")).toBeDefined();
    expect(screen.getByRole("region", { name: "Frutta" })).toBeDefined();
  });

  it("dice cosa fare quando la dispensa è vuota", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [[], 200]));
    renderScreen();
    expect(await screen.findByRole("heading", { name: "Dispensa vuota" })).toBeDefined();
  });

  it("un caricamento fallito non si traveste da dispensa vuota, e offre «Riprova»", async () => {
    let calls = 0;
    stubRoutedFetch((path) => {
      if (path.includes("/shopping-list")) return [[], 200];
      calls += 1;
      return calls === 1 ? [{ detail: "no" }, 500] : [ITEMS, 200];
    });
    renderScreen();
    expect(await screen.findByText("Non sono riuscito a caricare la dispensa.")).toBeDefined();
    expect(screen.queryByRole("heading", { name: "Dispensa vuota" })).toBeNull();
    // senza un caricamento riuscito prima non c'è niente da mostrare sotto l'errore
    expect(screen.queryByText(/ultimo caricamento/)).toBeNull();
    expect(screen.queryByRole("region")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("Total 0%")).toBeDefined();
  });

  it("un aggiornamento fallito lo dice, e lascia la dispensa dell'ultimo caricamento", async () => {
    // React Query tiene i dati di prima quando un nuovo caricamento fallisce: nasconderli
    // toglierebbe la dispensa proprio quando la rete è incerta, cioè in corsia
    let patched = false;
    stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (init?.method === "PATCH") {
        patched = true;
        return [{ ...ITEMS[0], status: "low" }, 200];
      }
      return patched ? [{ detail: "giù" }, 500] : [ITEMS, 200];
    });
    renderScreen();
    const gauge = await screen.findByRole("radiogroup", { name: "Quanto resta di Total 0%" });
    fireEvent.click(within(gauge).getByRole("radio", { name: "Quasi finito" }));
    expect(
      await screen.findByText(
        "Non sono riuscito ad aggiornare la dispensa. Quella qui sotto è dell'ultimo caricamento."
      )
    ).toBeDefined();
    expect(screen.queryByText("Non sono riuscito a caricare la dispensa.")).toBeNull();
    expect(screen.getByText("Total 0%")).toBeDefined();
    expect(screen.getByRole("link", { name: "Mela" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Riprova" })).toBeDefined();
  });

  // D3/CLAUDE.md, «mai un vicolo cieco»: un conteggio che non arriva toglie la
  // nota, non la strada. La dispensa risponde normalmente, solo la lista fallisce.
  it("se il conteggio della lista non arriva, l'ingresso a «Sistema la spesa» resta con una nota generica", async () => {
    stubRoutedFetch((path) =>
      path.includes("/shopping-list") ? [{ detail: "giù" }, 500] : [ITEMS, 200]
    );
    renderScreen();

    await screen.findByText("Total 0%"); // la dispensa è arrivata
    const link = screen.getByRole("link", { name: /Sistema la spesa/ });
    expect(link.getAttribute("href")).toBe("/sistema");
    expect(link).not.toHaveClass("bg-low-tint");
    expect(screen.getByText("Metti via quello che hai comprato")).toBeDefined();
  });

  it("toccare una tacca manda lo stato, non la posizione", async () => {
    const fetchSpy = stubRoutedFetch((path, init) =>
      init?.method === "PATCH" ? [{ ...ITEMS[0], status: "low" }, 200] : path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();
    const gauge = await screen.findByRole("radiogroup", { name: "Quanto resta di Total 0%" });
    fireEvent.click(within(gauge).getByRole("radio", { name: "Quasi finito" }));
    await waitFor(() => {
      const patch = fetchSpy.mock.calls.find(([, init]) => init?.method === "PATCH");
      // ITEMS[0] è "p1": la voce toccata, non un'altra con lo stesso ingrediente
      expect(String(patch?.[0])).toMatch(/\/pantry\/p1$/);
      expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ status: "low" });
    });
  });

  it("la ✕ toglie la voce e l'avviso offre «Annulla», che la disarchivia", async () => {
    const fetchSpy = stubRoutedFetch((path, init) =>
      init?.method === "PATCH" ? [ITEMS[0], 200] : path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    expect(await screen.findByText("Tolto dalla dispensa: Total 0%")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    await waitFor(() => {
      const patches = fetchSpy.mock.calls.filter(([, init]) => init?.method === "PATCH");
      expect(patches.map(([, init]) => JSON.parse(String(init?.body)))).toEqual([
        { archived: true },
        { archived: false },
      ]);
      // tutte e due sulla voce toccata, "p1": l'annulla rimette quella, non un'altra
      expect(patches.map(([url]) => String(url).match(/\/pantry\/[^/?]+$/)?.[0])).toEqual([
        "/pantry/p1",
        "/pantry/p1",
      ]);
    });
  });

  it("la riga resta bloccata finché il riordino dopo la ✕ non è arrivato (regressione)", async () => {
    // la PATCH torna subito, ma il GET che `invalidate()` lancia in `onSuccess` resta
    // appeso finché non lo sblocchiamo: se `onSuccess` non ne aspetta la promise, React
    // Query lascia `isPending` prima che il riordino sia arrivato, e la riga si sblocca
    // con la voce ancora a video. Non passa da `stubRoutedFetch`, che risponde solo in
    // modo sincrono: qui serve poter tenere il refetch appeso a piacere
    let releaseGet: (response: Response) => void = () => {};
    let getCalls = 0;
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      const path = String(url);
      if (init?.method === "PATCH") {
        return Promise.resolve(new Response(JSON.stringify(ITEMS[0]), { status: 200 }));
      }
      if (path.includes("/shopping-list")) return Promise.resolve(new Response("[]", { status: 200 }));
      getCalls += 1;
      if (getCalls === 1) return Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }));
      return new Promise<Response>((resolve) => { releaseGet = resolve; });
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    await screen.findByText("Tolto dalla dispensa: Total 0%");
    // la PATCH è tornata (l'avviso lo prova), ma il refetch è ancora appeso: la riga
    // deve restare bloccata
    const row = screen.getByText("Total 0%").closest("li")!;
    expect(within(row).getByRole("radio", { name: "Disponibile" })).toHaveAttribute("aria-disabled", "true");
    expect(within(row).getByRole("button", { name: "Togli Total 0% dalla dispensa" })).toHaveAttribute("aria-disabled", "true");
    // e un secondo tocco sulla ✕ stessa, ancora in volo, non ne parte un altro (`await act`:
    // vedi il commento sull'altro test di questo file)
    fireEvent.click(within(row).getByRole("radio", { name: "Finito" }));
    await act(async () => {});
    fireEvent.click(within(row).getByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    await act(async () => {});
    expect(spy.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
    releaseGet(new Response(JSON.stringify(ITEMS.filter((i) => i.id !== "p1")), { status: 200 }));
    await waitFor(() => expect(screen.queryByText("Total 0%")).toBeNull());
  });

  it("un annulla che fallisce lo dice nell'avviso e offre di riprovare", async () => {
    let patches = 0;
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        patches += 1;
        return patches === 2 ? [{ detail: "no" }, 500] : [ITEMS[0], 200];
      }
      return path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200];
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    fireEvent.click(await screen.findByRole("button", { name: "Annulla" }));
    expect(await screen.findByText("Non sono riuscito a rimettere Total 0% in dispensa.")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Riprova" }));
    await waitFor(() => expect(patches).toBe(3));
  });

  it("una ✕ che fallisce lo dice accanto alla voce, e la voce resta", async () => {
    stubRoutedFetch((path, init) =>
      init?.method === "PATCH" ? [{ detail: "no" }, 500] : path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    expect(await screen.findByRole("alert")).toBeDefined();
    // i due barattoli di yogurt greco sono ancora lì tutti e due
    expect(screen.getAllByRole("link", { name: "Yogurt greco" })).toHaveLength(2);
  });

  it("«In lista» su una voce finita la rimette in lista e lo dice", async () => {
    const finished = [{ ...ITEMS[2], status: "finished" }];
    const fetchSpy = stubRoutedFetch((path) =>
      path.includes("/restock") ? [{ added: true }, 200] : path.includes("/shopping-list") ? [[], 200] : [finished, 200]
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "In lista" }));
    expect(await screen.findByText("Rimesso in lista: mela")).toBeDefined();
    expect(fetchSpy.mock.calls.some(([url, init]) => String(url).includes("/pantry/p3/restock") && init?.method === "POST")).toBe(true);
  });

  it("un rientro in lista che fallisce lo dice nella riga, e «In lista» resta per riprovare", async () => {
    const finished = [{ ...ITEMS[2], status: "finished" }];
    stubRoutedFetch((path) =>
      path.includes("/restock") ? [{ detail: "no" }, 500] : path.includes("/shopping-list") ? [[], 200] : [finished, 200]
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "In lista" }));
    const row = screen.getByRole("link", { name: "Mela" }).closest("li")!;
    expect(await within(row).findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
    // `not.toBeDisabled` passerebbe sempre, ora che il pulsante si spegne con
    // `aria-disabled`: si guarda l'attributo che conta
    expect(within(row).getByRole("button", { name: "In lista" })).not.toHaveAttribute("aria-disabled");
  });

  it("se era già in lista, l'avviso lo dice", async () => {
    const finished = [{ ...ITEMS[2], status: "finished" }];
    stubRoutedFetch((path) =>
      path.includes("/restock") ? [{ added: false }, 200] : path.includes("/shopping-list") ? [[], 200] : [finished, 200]
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "In lista" }));
    expect(await screen.findByText("Era già in lista.")).toBeDefined();
  });

  it("una voce finita che ha già una voce aperta in lista non offre «In lista»", async () => {
    const finished = [{ ...ITEMS[2], status: "finished" }];
    const list = [{ id: "s1", raw_text: "mela", ingredient_id: "i2", ingredient_name: "mela",
      ingredient_category: "frutta", ingredient_kind: "food", status: "pending", reason: "manual",
      created_at: "2026-09-11T10:00:00Z" }];
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [list, 200] : [finished, 200]));
    renderScreen();
    expect(await screen.findByText("Già in lista")).toBeDefined();
    expect(screen.queryByRole("button", { name: "In lista" })).toBeNull();
  });

  // CLAUDE.md, lezione 1: `PantryRow.test.tsx` prova solo l'argomento passato a un
  // `onExpiry` finto. Qui si prova la mutazione `expiry` vera di questo schermo: la
  // PATCH reale, per la voce giusta, col corpo giusto — compresa la cancellazione,
  // che deve restare `{ expires_on: null }` e mai `{}` (il backend rifiuta un corpo
  // vuoto con 400).
  it("scrivere una scadenza manda una PATCH alla voce giusta, col corpo giusto", async () => {
    const fetchSpy = stubRoutedFetch((path, init) =>
      init?.method === "PATCH"
        ? [{ ...ITEMS[0], expires_on: "2026-10-05" }, 200]
        : path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();

    const row = (await screen.findByText("Total 0%")).closest("li")!;
    fireEvent.click(within(row).getByRole("button", { name: /scadenza/i }));
    const field = within(row).getByLabelText(/scadenza/i);
    fireEvent.change(field, { target: { value: "2026-10-05" } });
    fireEvent.blur(field);

    await waitFor(() => {
      const patch = fetchSpy.mock.calls.find(([, init]) => init?.method === "PATCH");
      // ITEMS[0] ha id "p1": senza questa riga nessuna asserzione distinguerebbe
      // una PATCH mandata per la voce sbagliata
      expect(String(patch?.[0])).toContain("/pantry/p1");
      expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ expires_on: "2026-10-05" });
    });
  });

  it("svuotare il campo manda null, non un corpo vuoto", async () => {
    const fetchSpy = stubRoutedFetch((path, init) =>
      init?.method === "PATCH"
        ? [{ ...ITEMS[2], expires_on: null, expiry: null }, 200]
        : path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();

    const row = (await screen.findByText("Mela")).closest("li")!;
    fireEvent.click(within(row).getByRole("button", { name: /scadenza/i }));
    const field = within(row).getByLabelText(/scadenza/i);
    fireEvent.change(field, { target: { value: "" } });
    fireEvent.blur(field);

    await waitFor(() => {
      const patch = fetchSpy.mock.calls.find(([, init]) => init?.method === "PATCH");
      expect(String(patch?.[0])).toContain("/pantry/p3");
      expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ expires_on: null });
    });
  });

  it("una scrittura della scadenza rifiutata lo dice accanto alla voce giusta", async () => {
    stubRoutedFetch((path, init) =>
      init?.method === "PATCH"
        ? [{ detail: "no" }, 500]
        : path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();

    const row = (await screen.findByText("Total 0%")).closest("li")!;
    fireEvent.click(within(row).getByRole("button", { name: /scadenza/i }));
    const field = within(row).getByLabelText(/scadenza/i);
    fireEvent.change(field, { target: { value: "2026-10-05" } });
    fireEvent.blur(field);

    expect(await within(row).findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
    const other = screen.getByText("Pesca").closest("li")!;
    expect(within(other).queryByRole("alert")).toBeNull();
  });

  it("«Scansiona» apre lo scanner sotto la barra, con le righe a video, e la ✕ lo chiude (S3)", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.click(screen.getByRole("button", { name: "Scansiona" }));
    expect(screen.getByRole("heading", { name: "Codice a barre" })).toBeDefined();
    expect(screen.getByText("Total 0%")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Chiudi l'aggiunta" }));
    expect(screen.queryByRole("heading", { name: "Codice a barre" })).toBeNull();
  });

  it("«Annulla» nell'avviso toglie la voce appena entrata (S3)", async () => {
    const created = { ...ITEMS[2], id: "p9" };
    const spy = stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (path.includes("/ingredients")) return [[MELA], 200];
      if (init?.method === "POST") return [created, 201];
      if (init?.method === "PATCH") return [created, 200];
      return [ITEMS, 200];
    });
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mel" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(await screen.findByRole("option", { name: "Mela" }));
    fireEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    expect(await screen.findByText("In dispensa: Mela")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    await vi.waitFor(() => {
      const patch = spy.mock.calls.find(([, init]) => init?.method === "PATCH");
      expect(String(patch?.[0])).toContain("/pantry/p9");
      expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ archived: true });
    });
  });
});

describe("PantryScreen, «Tutto / Cibo / Casa» (S14)", () => {
  it("con un mondo solo il selettore non c'è, e vale «Tutto» anche se la sessione ricordava «Casa»", async () => {
    sessionStorage.setItem("spena.dispensa.mondo", "non_food");
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    expect(screen.queryByRole("group", { name: "Cosa mostrare" })).toBeNull();
    // «Casa» su una dispensa di solo cibo l'avrebbe svuotata: è tutto a video, e la
    // sessione ora ricorda «Tutto»
    expect(screen.getByText("Pesca")).toBeDefined();
    expect(screen.getByRole("link", { name: "Mela" })).toBeDefined();
    await waitFor(() => expect(sessionStorage.getItem("spena.dispensa.mondo")).toBe("all"));
  });

  it("con cibo e casa, «Tutto» è premuto, e «Casa» e «Cibo» mostrano un mondo solo", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [DUE_MONDI, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    expect(mondo("Tutto").getAttribute("aria-pressed")).toBe("true");
    expect(mondo("Casa").getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByRole("link", { name: "Detersivo per i piatti" })).toBeDefined();

    fireEvent.click(mondo("Casa"));
    expect(mondo("Casa").getAttribute("aria-pressed")).toBe("true");
    expect(mondo("Tutto").getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByRole("link", { name: "Detersivo per i piatti" })).toBeDefined();
    expect(screen.queryByText("Total 0%")).toBeNull();
    expect(screen.queryByRole("link", { name: "Mela" })).toBeNull();
    // il reparto del cibo non è chiuso: non c'è
    expect(screen.queryByRole("heading", { name: "Latticini" })).toBeNull();

    fireEvent.click(mondo("Cibo"));
    expect(screen.getByText("Total 0%")).toBeDefined();
    expect(screen.getByRole("link", { name: "Mela" })).toBeDefined();
    expect(screen.queryByRole("link", { name: "Detersivo per i piatti" })).toBeNull();
  });

  it("la scelta si ricorda nella sessione: riaperta la Dispensa, è ancora lì", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [DUE_MONDI, 200]));
    const { unmount } = renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.click(mondo("Cibo"));
    expect(sessionStorage.getItem("spena.dispensa.mondo")).toBe("food");
    unmount();

    renderScreen();
    await screen.findByText("Total 0%");
    expect(mondo("Cibo").getAttribute("aria-pressed")).toBe("true");
    expect(screen.queryByRole("link", { name: "Detersivo per i piatti" })).toBeNull();
  });

  it("il riepilogo delle scadenze conta il mondo scelto", async () => {
    const detersivoInScadenza = { ...DETERSIVO, expires_on: "2026-09-28", expiry: "soon" };
    stubRoutedFetch((path) =>
      path.includes("/shopping-list") ? [[], 200] : [[...ITEMS, detersivoInScadenza], 200]
    );
    renderScreen();
    expect(await screen.findByRole("button", { name: "2 in scadenza questa settimana" })).toBeDefined();
    fireEvent.click(mondo("Casa"));
    expect(screen.getByRole("button", { name: "1 in scadenza questa settimana" })).toBeDefined();
    fireEvent.click(mondo("Cibo"));
    expect(screen.getByRole("button", { name: "1 in scadenza questa settimana" })).toBeDefined();
  });

  it("in un mondo senza scadenze il riepilogo non c'è, e il suo filtro premuto si spegne", async () => {
    // in DUE_MONDI scade solo la mela
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [DUE_MONDI, 200]));
    renderScreen();
    const summary = await screen.findByRole("button", { name: "1 in scadenza questa settimana" });
    fireEvent.click(summary);
    expect(summary.getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(mondo("Casa"));
    expect(screen.queryByRole("button", { name: /in scadenza/ })).toBeNull();
    // il detersivo, senza scadenza, è a video: il filtro se n'è andato col suo riepilogo
    expect(screen.getByRole("link", { name: "Detersivo per i piatti" })).toBeDefined();

    fireEvent.click(mondo("Tutto"));
    expect(
      screen.getByRole("button", { name: "1 in scadenza questa settimana" }).getAttribute("aria-pressed")
    ).toBe("false");
  });

  it("una ricerca che nel mondo scelto non trova niente offre «Cerca in tutto», che tiene il testo", async () => {
    stubRoutedFetch((path) =>
      path.includes("/shopping-list") ? [[], 200] : path.includes("/ingredients") ? [[], 200] : [DUE_MONDI, 200]
    );
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.click(mondo("Casa"));
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mela" } });

    expect(screen.getByRole("heading", { name: "Niente in Casa per «mela»" })).toBeDefined();
    // la mela c'è, sotto «Cibo»: «Niente in dispensa» sarebbe falso, e «Aggiungi» ne
    // farebbe un doppione
    expect(screen.queryByRole("heading", { name: /Niente in dispensa/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Aggiungi «mela»" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Cerca in tutto" }));
    expect(mondo("Tutto").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByLabelText("Cerca o aggiungi in dispensa")).toHaveProperty("value", "mela");
    expect(screen.getByRole("link", { name: "Mela" })).toBeDefined();
  });

  it("togliere l'ultima cosa di casa mentre si guarda «Casa» torna a «Tutto», e il selettore se ne va", async () => {
    let archived = false;
    stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (init?.method === "PATCH") {
        archived = JSON.parse(String(init.body)).archived;
        return [DETERSIVO, 200];
      }
      return [archived ? ITEMS : DUE_MONDI, 200];
    });
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.click(mondo("Casa"));
    fireEvent.click(screen.getByRole("button", { name: "Togli detersivo per i piatti dalla dispensa" }));

    await waitFor(() => expect(screen.queryByRole("group", { name: "Cosa mostrare" })).toBeNull());
    // non una dispensa vuota per un filtro che non si vede più: il cibo è tutto lì
    expect(screen.getByText("Total 0%")).toBeDefined();
    expect(screen.queryByRole("heading", { name: "Dispensa vuota" })).toBeNull();
    expect(sessionStorage.getItem("spena.dispensa.mondo")).toBe("all");
  });

  it("una voce aggiunta dell'altro mondo porta il selettore a «Tutto», e va in vista", async () => {
    const created = { ...ITEMS[2], id: "p9" };
    let added = false;
    // gesto dell'aggiunta: le risposte finte
    stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (path.includes("/ingredients")) return [[MELA], 200];
      if (init?.method === "POST") {
        added = true;
        return [created, 201];
      }
      return [added ? [...DUE_MONDI, created] : DUE_MONDI, 200];
    });
    const scrollSpy = vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(() => {});
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.click(mondo("Casa"));

    // gesto dell'aggiunta: dal + della barra, una mela (cibo) mentre si guarda «Casa»
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mel" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(await screen.findByRole("option", { name: "Mela" }));
    // la scheda di conferma (S3): un tocco in più
    fireEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    expect(await screen.findByText("In dispensa: Mela")).toBeDefined();

    await waitFor(() => expect(mondo("Tutto").getAttribute("aria-pressed")).toBe("true"));
    await waitFor(() => expect(scrollSpy).toHaveBeenCalledTimes(1));
    scrollSpy.mockRestore();
  });

  it("una voce aggiunta dello stesso mondo lascia il mondo com'è", async () => {
    // deciso da Mattia il 2026-10-09 (piano S14, «Decisioni prese»): la bozza dice solo
    // dell'altro mondo; qui il mondo resta, perché la riga nuova si vede già
    const created = { ...ITEMS[2], id: "p9" };
    let added = false;
    // gesto dell'aggiunta: le risposte finte
    stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (path.includes("/ingredients")) return [[MELA], 200];
      if (init?.method === "POST") {
        added = true;
        return [created, 201];
      }
      return [added ? [...DUE_MONDI, created] : DUE_MONDI, 200];
    });
    const scrollSpy = vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(() => {});
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.click(mondo("Cibo"));

    // gesto dell'aggiunta: dal + della barra, una mela (cibo) mentre si guarda «Cibo»
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mel" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(await screen.findByRole("option", { name: "Mela" }));
    // la scheda di conferma (S3): un tocco in più
    fireEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    expect(await screen.findByText("In dispensa: Mela")).toBeDefined();

    await waitFor(() => expect(scrollSpy).toHaveBeenCalledTimes(1));
    expect(mondo("Cibo").getAttribute("aria-pressed")).toBe("true");
    scrollSpy.mockRestore();
  });

  it("un tocco sul selettore spegne la riga da portare in vista: il mondo non rimbalza a «Tutto»", async () => {
    // il caso: su «Casa» si aggiunge una mela, e prima che la dispensa riletta la contenga si
    // scrive «det» nella barra. Quando la mela arriva il mondo va a «Tutto» (settleWorld), ma
    // la sua riga è filtrata via dalla ricerca e non monta: nessuno spegne `revealId`
    const created = { ...ITEMS[2], id: "p9" };
    let added = false;
    let releaseRefetch: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      releaseRefetch = resolve;
    });
    const respond = (body: unknown, status: number) =>
      new Response(JSON.stringify(body), { status });
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown, init?: RequestInit) => {
        const path = String(url);
        if (path.includes("/shopping-list")) return Promise.resolve(respond([], 200));
        if (path.includes("/ingredients")) return Promise.resolve(respond([MELA], 200));
        if (init?.method === "POST") {
          added = true;
          return Promise.resolve(respond(created, 201));
        }
        // la dispensa riletta dopo l'aggiunta aspetta che il test la liberi
        if (added) return gate.then(() => respond([...DUE_MONDI, created], 200));
        return Promise.resolve(respond(DUE_MONDI, 200));
      })
    );
    vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(() => {});
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.click(mondo("Casa"));

    // gesto dell'aggiunta: dal + della barra, una mela (cibo) mentre si guarda «Casa»
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mel" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(await screen.findByRole("option", { name: "Mela" }));
    fireEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    expect(await screen.findByText("In dispensa: Mela")).toBeDefined();

    // la dispensa riletta non è ancora arrivata: si scrive un testo che la mela non soddisfa
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "det" } });
    await act(async () => {
      releaseRefetch();
    });

    // la voce nuova è arrivata: il mondo va a «Tutto», come deve
    await waitFor(() => expect(mondo("Tutto").getAttribute("aria-pressed")).toBe("true"));
    expect(screen.getByText("Detersivo per i piatti")).toBeDefined();

    // un tocco su «Casa» è una scelta di chi guarda: deve restare lì
    fireEvent.click(mondo("Casa"));
    await waitFor(() => expect(mondo("Casa").getAttribute("aria-pressed")).toBe("true"));
    expect(mondo("Tutto").getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByText("Detersivo per i piatti")).toBeDefined();
  });
});

// --- S15: i reparti che si aprono e si chiudono ---

const CHIUSI = "spena.dispensa.reparti-chiusi";

/** I reparti chiusi che la Dispensa ha salvato, in ordine. */
function chiusiSalvati(): string[] {
  return (JSON.parse(localStorage.getItem(CHIUSI) ?? "[]") as string[]).sort();
}

/** Il nome del titolo di un reparto, con gli spazi che il calcolo del nome accessibile
 * mette o non mette fra un elemento e l'altro: «Latticini 2 · 1 finito». */
function titolo(testo: string): RegExp {
  return new RegExp(`^${testo.split(" ").join("\\s+")}$`);
}

/** Il pulsante del titolo di un reparto: il primo pulsante della sua regione, che si
 * chiama col solo nome del reparto, aperta e chiusa. Non per nome del pulsante: «Casa»
 * è anche un mondo di S14. */
function reparto(nome: string): HTMLElement {
  return within(screen.getByRole("region", { name: nome })).getAllByRole("button")[0];
}

describe("PantryScreen, i reparti che si chiudono (S15)", () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("toccare il titolo chiude il reparto e lo ricorda; chiuso dice quante voci ha e quali chiedono attenzione", async () => {
    const rows = [
      { ...ITEMS[0], status: "finished" },
      { ...ITEMS[1], expires_on: "2026-09-29", expiry: "soon" },
      ITEMS[2],
    ];
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [rows, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    const latticini = reparto("Latticini");
    expect(latticini).toHaveAttribute("aria-expanded", "true");
    // aperto, il titolo dice il numero e basta: le righe sono lì sotto
    expect(latticini).toHaveAccessibleName(titolo("Latticini 2"));

    fireEvent.click(latticini);
    expect(latticini).toHaveAttribute("aria-expanded", "false");
    expect(latticini).toHaveAccessibleName(titolo("Latticini 2 · 1 finito · 1 in scadenza"));
    // le righe chiuse escono dalla pagina accessibile, tacche e ✕ comprese
    expect(screen.queryByRole("link", { name: "Yogurt greco" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Togli Total 0% dalla dispensa" })).toBeNull();
    // gli altri reparti non si toccano
    expect(screen.getByRole("link", { name: "Mela" })).toBeDefined();
    expect(chiusiSalvati()).toEqual(["latticini"]);

    fireEvent.click(latticini);
    expect(latticini).toHaveAttribute("aria-expanded", "true");
    expect(screen.getAllByRole("link", { name: "Yogurt greco" })).toHaveLength(2);
    expect(chiusiSalvati()).toEqual([]);
  });

  it("un reparto chiuso resta chiuso tornando in dispensa", async () => {
    localStorage.setItem(CHIUSI, JSON.stringify(["frutta"]));
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    expect(reparto("Frutta")).toHaveAccessibleName(titolo("Frutta 1 · 1 in scadenza"));
    expect(screen.queryByRole("link", { name: "Mela" })).toBeNull();
    expect(reparto("Latticini")).toHaveAttribute("aria-expanded", "true");
  });

  it("una ricerca apre i reparti chiusi che hanno un risultato, senza cambiare quel che è salvato", async () => {
    localStorage.setItem(CHIUSI, JSON.stringify(["frutta", "latticini"]));
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByRole("region", { name: "Frutta" });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");

    const barra = screen.getByLabelText("Cerca o aggiungi in dispensa");
    fireEvent.change(barra, { target: { value: "mel" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "Mela" })).toBeDefined();
    expect(chiusiSalvati()).toEqual(["frutta", "latticini"]);

    // cancellata la ricerca, la dispensa torna com'era stata lasciata
    fireEvent.change(barra, { target: { value: "" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    expect(reparto("Latticini")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: "Mela" })).toBeNull();
  });

  it("il riepilogo delle scadenze premuto apre i reparti con una scadenza, senza salvare", async () => {
    localStorage.setItem(CHIUSI, JSON.stringify(["frutta"]));
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    const riepilogo = await screen.findByRole("button", { name: "1 in scadenza questa settimana" });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(riepilogo);
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "Mela" })).toBeDefined();
    expect(chiusiSalvati()).toEqual(["frutta"]);

    fireEvent.click(riepilogo);
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
  });

  it("durante una ricerca il titolo chiude e apre per davvero, e si salva", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    const barra = screen.getByLabelText("Cerca o aggiungi in dispensa");

    fireEvent.change(barra, { target: { value: "mel" } });
    fireEvent.click(reparto("Frutta"));
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    expect(chiusiSalvati()).toEqual(["frutta"]);
    // la stessa ricerca, una lettera in più: quel che si è appena chiuso resta chiuso
    // (decisione 1 di Mattia del 2026-10-09: si rispetta il gesto finché la ricerca non si cancella)
    fireEvent.change(barra, { target: { value: "mela" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    // riaperto a mano durante la ricerca: aperto, e salvato aperto
    fireEvent.click(reparto("Frutta"));
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
    expect(chiusiSalvati()).toEqual([]);
    // cancellata la ricerca vale il salvato
    fireEvent.change(barra, { target: { value: "" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");

    // chiuso senza filtro, una ricerca nuova lo riapre come ogni reparto con un risultato
    fireEvent.click(reparto("Frutta"));
    fireEvent.change(barra, { target: { value: "mel" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
    fireEvent.change(barra, { target: { value: "" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
  });

  it("con lo spazio del sito bloccato i reparti partono aperti, e si chiudono lo stesso", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloccato");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloccato");
    });
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(reparto("Frutta"));
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: "Mela" })).toBeNull();
  });
});
