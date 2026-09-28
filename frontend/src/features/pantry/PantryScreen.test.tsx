import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { PantryScreen } from "./PantryScreen";

const ITEMS = [
  { id: "p1", ingredient_id: "i1", product_id: "pr1", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Total 0%", product_brand: "Fage",
    status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z",
    expires_on: null, expiry: null },
  { id: "p2", ingredient_id: "i1", product_id: "pr2", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Pesca", product_brand: "Carrefour",
    status: "low", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z",
    expires_on: null, expiry: null },
  { id: "p3", ingredient_id: "i2", product_id: null, ingredient_name: "mela",
    ingredient_category: "frutta", product_name: null, product_brand: null,
    status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z",
    expires_on: "2026-09-28", expiry: "soon" },
];

const MELA = { id: "i2", name: "mela", display_name: "Mela", category: "frutta" };

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
    expect(await screen.findByText("mela")).toBeDefined();
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

    await waitFor(() => expect(within(row).getByRole("radio", { name: "Disponibile" })).toBeDisabled());
    expect(within(row).getByRole("button", { name: "Togli Total 0% dalla dispensa" })).toBeDisabled();
    const other = screen.getByText("Pesca").closest("li")!;
    expect(within(other).getByRole("radio", { name: "Disponibile" })).not.toBeDisabled();
  });

  it("scrivere nella barra filtra le righe, anche per prodotto e marca", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "fage" } });
    expect(screen.getByText("Total 0%")).toBeDefined();
    expect(screen.queryByText("Pesca")).toBeNull();
    expect(screen.queryByRole("link", { name: "mela" })).toBeNull();
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
    expect(await screen.findByText("In dispensa: Mela")).toBeDefined();
    const post = fetchSpy.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ ingredient_id: "i2", status: "available" });
    // l'aggiunta si chiude e la barra torna vuota
    expect(screen.queryByLabelText("Ingrediente da mettere in dispensa")).toBeNull();
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
    expect(await screen.findByText("Non sono riuscito ad aggiungere la voce in dispensa. Riprova.")).toBeDefined();
    expect(screen.getByLabelText("Ingrediente da mettere in dispensa")).toBeDefined();
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
    expect(screen.getByRole("link", { name: "mela" })).toBeDefined();
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
    const row = screen.getByRole("link", { name: "mela" }).closest("li")!;
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
    expect(screen.queryByRole("button", { name: "Aggiungi «sale»" })).toBeNull();
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
    fireEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("Total 0%")).toBeDefined();
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
      const bodies = fetchSpy.mock.calls
        .filter(([, init]) => init?.method === "PATCH")
        .map(([, init]) => JSON.parse(String(init?.body)));
      expect(bodies).toEqual([{ archived: true }, { archived: false }]);
    });
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
    expect(screen.getAllByRole("link", { name: "yogurt greco" })).toHaveLength(2);
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

    const row = (await screen.findByText("mela")).closest("li")!;
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
});
