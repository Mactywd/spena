import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { PantryScreen } from "./PantryScreen";

const ITEMS = [
  { id: "p1", ingredient_id: "i1", product_id: "pr1", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Total 0%", product_brand: "Fage",
    status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z" },
  { id: "p2", ingredient_id: "i1", product_id: "pr2", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Pesca", product_brand: "Carrefour",
    status: "low", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z" },
  { id: "p3", ingredient_id: "i2", product_id: null, ingredient_name: "mela",
    ingredient_category: "frutta", product_name: null, product_brand: null,
    status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z" },
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

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PantryScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("PantryScreen", () => {
  it("mostra marca e nome del prodotto quando li conosce", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(ITEMS), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("Total 0%")).toBeDefined();
    expect(screen.getByText("Fage")).toBeDefined();
  });

  it("nome e marca restano due parole anche per chi legge con la voce", async () => {
    // `ml-2` spaziava solo in orizzontale: il nome accessibile della riga si
    // leggeva «Total 0%Fage», cioè una parola inventata
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(ITEMS), { status: 200 })
    ));
    renderScreen();
    const row = (await screen.findByText("Total 0%")).closest("li")!;
    expect(row.textContent).toContain("Total 0% Fage");
  });

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

  it("spostare il cursore manda la posizione, non lo stato", async () => {
    // lo stato lo ricava il backend: mandarlo da qui vorrebbe dire avere due
    // opinioni su cosa sia «quasi finito»
    const fetchMock = stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], status: "low", fill_percent: 15 }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "15" } });
    fireEvent.pointerUp(cursore);

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "PATCH");
      // ITEMS[2] (mela) ha id "p3": senza questa riga il ramo PATCH dello stub
      // sarebbe decorativo, perché nessuna asserzione lo distinguerebbe da una
      // PATCH mandata per la voce sbagliata
      expect(String(patch![0])).toContain("/pantry/p3");
      expect(JSON.parse(String((patch![1] as RequestInit).body))).toEqual({ fill_percent: 15 });
    });
  });

  it("una voce che non ha mai visto il cursore parte dalla zona del suo stato", async () => {
    // `fill_percent` resta null: non si inventa una misura per riempire un buco
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di Pesca" });
    // ITEMS[1] è `low`: metà della zona gialla
    expect((cursore as HTMLInputElement).value).toBe("15");
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
    const cursore = within(row).getByRole("slider");
    fireEvent.change(cursore, { target: { value: "10" } });
    fireEvent.pointerUp(cursore);

    expect(await within(row).findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
    const other = screen.getByText("Pesca").closest("li")!;
    expect(within(other).queryByRole("alert")).toBeNull();
  });

  it("si può togliere una voce dalla dispensa", async () => {
    const spy = vi.fn().mockImplementation((_url: string, init?: RequestInit) =>
      init?.method === "PATCH"
        ? Promise.resolve(new Response(JSON.stringify(ITEMS[0]), { status: 200 }))
        : Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    const row = (await screen.findByText("Total 0%")).closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Togli Total 0% dalla dispensa" }));

    const patch = spy.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(patch?.[0]).toContain("/pantry/p1");
    expect(JSON.parse(patch?.[1].body)).toEqual({ archived: true });
  });

  it("mentre una modifica è in volo i controlli di quella voce sono bloccati", async () => {
    // due PATCH sulla stessa voce arrivano in ordine ignoto e l'ultima a rispondere
    // vince: la seconda non deve nemmeno poter partire
    const spy = vi.fn().mockImplementation((_url: string, init?: RequestInit) =>
      init?.method === "PATCH"
        ? new Promise<Response>(() => {})
        : Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    const row = (await screen.findByText("Total 0%")).closest("li")!;
    const cursore = within(row).getByRole("slider");
    fireEvent.change(cursore, { target: { value: "10" } });
    fireEvent.pointerUp(cursore);

    await waitFor(() => expect(within(row).getByRole("slider")).toBeDisabled());
    expect(within(row).getByRole("button", { name: "Togli Total 0% dalla dispensa" })).toBeDisabled();
    const other = screen.getByText("Pesca").closest("li")!;
    expect(within(other).getByRole("slider")).not.toBeDisabled();
  });

  // M2, spec §8.3: l'ingresso diretto. Senza, per mettere in dispensa una cosa
  // comprata e non scritta in lista bisognava inventare una voce di lista,
  // spuntarla e sistemarla — e lo schermo prometteva «aggiungi qualcosa a mano»
  // da quando esisteva.
  it("si può aggiungere in dispensa qualcosa che non era in lista", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (path.includes("/ingredients/search")) return [[MELA], 200];
      if (init?.method === "POST") return [{ ...ITEMS[2] }, 201];
      return [[], 200];
    });

    renderScreen();
    await userEvent.type(await screen.findByLabelText("Aggiungi in dispensa"), "mel");
    await userEvent.click(await screen.findByRole("option", { name: /Mela/ }));

    const post = spy.mock.calls.find(([, init]) => (init as RequestInit)?.method === "POST");
    expect(String(post?.[0])).toContain("/pantry");
    expect(JSON.parse(String((post?.[1] as RequestInit).body))).toEqual({
      ingredient_id: "i2",
      status: "available",
    });
  });

  it("un'aggiunta rifiutata lo dice accanto al campo, non in cima allo schermo", async () => {
    stubRoutedFetch((path, init) => {
      if (path.includes("/ingredients/search")) return [[MELA], 200];
      if (init?.method === "POST") return [{ detail: "no" }, 500];
      return [[], 200];
    });

    renderScreen();
    await userEvent.type(await screen.findByLabelText("Aggiungi in dispensa"), "mel");
    await userEvent.click(await screen.findByRole("option", { name: /Mela/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/non sono riuscito ad aggiungere/i);
  });

  it("mentre l'aggiunta è in volo il campo non accetta una seconda scelta", async () => {
    // due POST in volo sulla stessa dispensa creano due voci per una sola cosa
    // comprata, e la seconda non si distingue dalla prima
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      const path = String(url);
      if (init?.method === "POST") return new Promise<Response>(() => {});
      const body = path.includes("/ingredients/search") ? [MELA] : [];
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.type(await screen.findByLabelText("Aggiungi in dispensa"), "mel");
    await userEvent.click(await screen.findByRole("option", { name: /Mela/ }));

    await waitFor(() => expect(screen.getByLabelText("Aggiungi in dispensa")).toBeDisabled());
  });

  it("dice cosa fare quando la dispensa è vuota", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderScreen();
    expect(await screen.findByText(/Dispensa vuota/)).toBeDefined();
  });

  it("un caricamento fallito non si traveste da dispensa vuota", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "errore" }), { status: 500 })
    ));
    renderScreen();
    expect(await screen.findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
    expect(screen.queryByText(/Dispensa vuota/)).toBeNull();
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

  it("la X toglie la voce dalla dispensa e lascia un annulla al suo posto", async () => {
    const fetchMock = stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], id: "p3" }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));

    const patch = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "PATCH");
    expect(JSON.parse(String((patch![1] as RequestInit).body))).toEqual({ archived: true });
    expect(await screen.findByText("Tolta dalla dispensa")).toBeDefined();
    expect(screen.getByRole("button", { name: "Annulla" })).toBeDefined();
  });

  it("annullare la rimette in dispensa con una PATCH che disarchivia", async () => {
    // il difetto che questo test difende: un annulla che si limita a nascondere la
    // lapide lascerebbe la voce archiviata sul server, e l'utente scoprirebbe di
    // averla persa solo al ricaricamento
    const fetchMock = stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") return [ITEMS[2], 200];
      return [ITEMS, 200];
    });
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));
    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));

    const corpi = fetchMock.mock.calls
      .filter(([, init]) => (init as RequestInit)?.method === "PATCH")
      .map(([, init]) => JSON.parse(String((init as RequestInit).body)));
    expect(corpi).toEqual([{ archived: true }, { archived: false }]);
    await waitFor(() => expect(screen.queryByText("Tolta dalla dispensa")).toBeNull());
  });

  it("passati i secondi dell'annulla la riga se ne va", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const utente = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    try {
      // la prima lettura deve avere la mela (altrimenti non c'è nulla da toccare);
      // solo dopo la PATCH il server smette di mandarla, come nella riga vera
      let archived = false;
      stubRoutedFetch((_path, init) => {
        if (init?.method === "PATCH") {
          archived = true;
          return [ITEMS[2], 200];
        }
        // dopo l'archiviazione il server non manda più la mela
        return [archived ? ITEMS.filter((item) => item.id !== "p3") : ITEMS, 200];
      });
      renderScreen();
      // la prima lettura è quella con la mela: la si aspetta prima di sostituirla
      await utente.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));
      expect(await screen.findByText("Tolta dalla dispensa")).toBeDefined();

      await vi.advanceTimersByTimeAsync(6000);

      await waitFor(() => expect(screen.queryByText("Tolta dalla dispensa")).toBeNull());
    } finally {
      vi.useRealTimers();
    }
  });

  it("una X che fallisce lo dice accanto alla voce, e la voce resta", async () => {
    stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") return [{ detail: "no" }, 500];
      return [ITEMS, 200];
    });
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));

    expect(await screen.findByText("Non sono riuscito a salvare la modifica. Riprova.")).toBeDefined();
    expect(screen.getByText("mela")).toBeDefined();
  });

  // Rilievo di revisione (a) sul Task 5: un annulla che fallisce archiviava
  // comunque la voce sul server. Invalidare a quel punto la faceva sparire dalla
  // lista senza lasciare né un messaggio né un modo di riprovare — un vicolo
  // cieco. La lapide deve restare, con l'errore dentro, e «Annulla» ripremibile.
  it("l'annulla che fallisce lascia una lapide con l'errore, e si può riprovare", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const utente = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    try {
      const fetchMock = stubRoutedFetch((_path, init) => {
        if (init?.method === "PATCH") {
          const body = JSON.parse(String(init!.body));
          if (body.archived === false) return [{ detail: "no" }, 500];
          return [{ ...ITEMS[2] }, 200];
        }
        return [ITEMS, 200];
      });
      renderScreen();

      await utente.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));
      expect(await screen.findByText("Tolta dalla dispensa")).toBeDefined();

      await utente.click(screen.getByRole("button", { name: "Annulla" }));

      expect(await screen.findByText("Non sono riuscito a salvare la modifica. Riprova.")).toBeDefined();
      // la lapide non è sparita: senza di lei l'annulla non avrebbe più un bersaglio
      expect(screen.getByText("Tolta dalla dispensa")).toBeDefined();
      expect(screen.getByRole("button", { name: "Annulla" })).toBeDefined();

      // il timer si è spento con l'errore: farlo scorrere non deve far sparire la
      // lapide mentre mostra l'errore, altrimenti sarebbe di nuovo un vicolo cieco
      await vi.advanceTimersByTimeAsync(6000);
      expect(screen.getByText("Tolta dalla dispensa")).toBeDefined();

      const corpi = fetchMock.mock.calls
        .filter(([, init]) => (init as RequestInit)?.method === "PATCH")
        .map(([, init]) => JSON.parse(String((init as RequestInit).body)));
      expect(corpi).toEqual([{ archived: true }, { archived: false }]);
    } finally {
      vi.useRealTimers();
    }
  });

  // Rilievo di revisione (b) sul Task 5: `removedId` era un solo id. Togliere una
  // seconda voce prima che scadesse la lapide della prima spegneva il timer della
  // prima (cleanup dello useEffect sulla dipendenza) e la faceva tornare viva
  // nell'interfaccia pur essendo già archiviata sul server — una riga fantasma.
  it("un ricaricamento fallito non si porta via la lapide, e l'annulla resta", async () => {
    // il ramo lasciato aperto dalla correzione della lapide: l'elenco tornava dal
    // server, quindi l'errore del server nascondeva l'elenco e con lui l'unico
    // annulla che esista. La voce è già archiviata davvero: senza quel tasto non
    // c'è nessun percorso nell'interfaccia per riportarla indietro.
    const archived = new Set<string>();
    let getFallisce = false;
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        const id = path.split("/").pop()!;
        const corpo = JSON.parse(String(init.body));
        if (corpo.archived === true) archived.add(id);
        else if (corpo.archived === false) archived.delete(id);
        // muovere il cursore invalida l'elenco: è la mutazione altrui che porta
        // lo schermo al ramo dell'errore mentre la lapide è a video
        else getFallisce = true;
        return [ITEMS.find((item) => item.id === id)!, 200];
      }
      if (getFallisce) return [{ detail: "boom" }, 500];
      return [ITEMS.filter((item) => !archived.has(item.id)), 200];
    });
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));
    expect(await screen.findByText("Tolta dalla dispensa")).toBeDefined();

    const cursore = screen.getByRole("slider", { name: "Quanto ne resta di Total 0%" });
    fireEvent.change(cursore, { target: { value: "15" } });
    fireEvent.pointerUp(cursore);

    expect(await screen.findByText(/Non sono riuscito a caricare la dispensa/)).toBeDefined();
    expect(screen.getByText("Tolta dalla dispensa")).toBeDefined();
    expect(screen.getByRole("button", { name: "Annulla" })).toBeDefined();
  });

  it("due rimozioni vicine non si calpestano: ognuna ha la sua lapide", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const utente = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    try {
      // il server vero non manda le voci archiviate (`list_pantry` filtra
      // `archived_at IS NULL`). Uno stub che le manda comunque finge che
      // archiviare non tolga la riga dalla GET, e nasconde il difetto: la lapide
      // viveva solo finché il server rimandava la sua riga, quindi la prima
      // invalidazione altrui la faceva svanire senza dire niente.
      const archived = new Set<string>();
      const fetchMock = stubRoutedFetch((path, init) => {
        if (init?.method === "PATCH") {
          const id = path.split("/").pop()!;
          // solo `archived` decide: il server vero non disarchivia per una PATCH
          // che parla d'altro (il cursore), e uno stub che lo facesse mentirebbe
          // al primo test che qui muovesse un cursore
          const corpo = JSON.parse(String(init.body));
          if (corpo.archived === true) archived.add(id);
          else if (corpo.archived === false) archived.delete(id);
          return [ITEMS.find((item) => item.id === id)!, 200];
        }
        return [ITEMS.filter((item) => !archived.has(item.id)), 200];
      });
      renderScreen();

      // A: la mela
      await utente.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));
      expect(await screen.findByText("Tolta dalla dispensa")).toBeDefined();

      // B, prima che scadano i sei secondi della mela
      await utente.click(await screen.findByRole("button", { name: "Togli Total 0% dalla dispensa" }));

      // le due lapidi convivono, ognuna con il suo annulla
      expect(screen.getAllByText("Tolta dalla dispensa")).toHaveLength(2);
      expect(screen.getAllByRole("button", { name: "Annulla" })).toHaveLength(2);

      // annullare la mela la riporta, senza toccare Total 0%
      const melaTomba = screen.getByText("mela").closest("li")!;
      await utente.click(within(melaTomba).getByRole("button", { name: "Annulla" }));

      await waitFor(() => expect(screen.getAllByText("Tolta dalla dispensa")).toHaveLength(1));
      const rimasta = screen.getByText("Tolta dalla dispensa").closest("li")!;
      expect(within(rimasta).getByText("Total 0%")).toBeDefined();

      const corpi = fetchMock.mock.calls
        .filter(([, init]) => (init as RequestInit)?.method === "PATCH")
        .map(([url, init]) => ({
          url: String(url),
          body: JSON.parse(String((init as RequestInit).body)),
        }));
      expect(corpi).toEqual([
        { url: expect.stringContaining("/p3"), body: { archived: true } },
        { url: expect.stringContaining("/p1"), body: { archived: true } },
        { url: expect.stringContaining("/p3"), body: { archived: false } },
      ]);
    } finally {
      vi.useRealTimers();
    }
  });

  // Rilievo della revisione finale: la lapide era resa dalla riga che arrivava dal
  // server, e il server non manda le voci archiviate. L'archiviazione non invalida
  // apposta, ma ogni ALTRA mutazione dello schermo sì: bastava muovere il cursore
  // di un'altra riga e la lapide svaniva muta a metà dei sei secondi, portandosi
  // via l'unico modo che l'interfaccia ha di disarchiviare.
  it("la lapide sopravvive a una mutazione su un'altra riga, e l'annulla funziona ancora", async () => {
    const archived = new Set<string>();
    const fetchMock = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        const id = path.split("/").pop()!;
        const body = JSON.parse(String(init.body));
        if (body.archived !== undefined) {
          if (body.archived) archived.add(id);
          else archived.delete(id);
        }
        return [ITEMS.find((item) => item.id === id)!, 200];
      }
      return [ITEMS.filter((item) => !archived.has(item.id)), 200];
    });
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));
    expect(await screen.findByText("Tolta dalla dispensa")).toBeDefined();

    // il cursore di un'altra riga: la sua PATCH invalida l'elenco, e la risposta
    // nuova non contiene più la mela
    const altra = screen.getByText("Total 0%").closest("li")!;
    const cursore = within(altra).getByRole("slider");
    fireEvent.change(cursore, { target: { value: "50" } });
    fireEvent.pointerUp(cursore);

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(
          ([, init]) => (init as RequestInit)?.method === undefined
        ).length
      ).toBeGreaterThan(2)
    );

    // la lapide è ancora lì, con il suo annulla
    expect(screen.getByText("Tolta dalla dispensa")).toBeDefined();
    const tomba = screen.getByText("mela").closest("li")!;
    await userEvent.click(within(tomba).getByRole("button", { name: "Annulla" }));

    await waitFor(() => expect(screen.queryByText("Tolta dalla dispensa")).toBeNull());
    const corpi = fetchMock.mock.calls
      .filter(([, init]) => (init as RequestInit)?.method === "PATCH")
      .map(([url, init]) => ({ url: String(url), body: JSON.parse(String((init as RequestInit).body)) }));
    expect(corpi).toContainEqual({
      url: expect.stringContaining("/p3"),
      body: { archived: false },
    });
    // e la mela è tornata viva nell'elenco
    expect(await screen.findByText("mela")).toBeDefined();
  });

  it("portato a zero il cursore chiede se rimettere la voce in lista", async () => {
    stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "0" } });
    fireEvent.pointerUp(cursore);

    expect(await screen.findByText("Lo rimetto in lista?")).toBeDefined();
    expect(screen.getByRole("button", { name: "Sì" })).toBeDefined();
    expect(screen.getByRole("button", { name: "No" })).toBeDefined();
  });

  it("finire una voce non scrive in lista da sé: solo il sì lo fa", async () => {
    // è il punto della decisione: nessuna sezione ne modifica un'altra in silenzio
    const fetchMock = stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
      if (init?.method === "POST") return [{ added: true }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "0" } });
    fireEvent.pointerUp(cursore);
    await screen.findByText("Lo rimetto in lista?");
    expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit)?.method === "POST")).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: "Sì" }));

    const post = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "POST");
    expect(String(post![0])).toContain("/pantry/p3/restock");
    expect(await screen.findByText("Rimesso in lista.")).toBeDefined();
  });

  it("se era già in lista lo dice, invece di far credere di aver aggiunto qualcosa", async () => {
    stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
      if (init?.method === "POST") return [{ added: false }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "0" } });
    fireEvent.pointerUp(cursore);
    await userEvent.click(await screen.findByRole("button", { name: "Sì" }));

    expect(await screen.findByText("Era già in lista.")).toBeDefined();
  });

  it("il no chiude la domanda e non scrive niente", async () => {
    const fetchMock = stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "0" } });
    fireEvent.pointerUp(cursore);
    await userEvent.click(await screen.findByRole("button", { name: "No" }));

    await waitFor(() => expect(screen.queryByText("Lo rimetto in lista?")).toBeNull());
    expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit)?.method === "POST")).toBe(false);
  });

  // «Mai un vicolo cieco»: un rientro in lista che fallisce deve dirlo accanto
  // alla voce e lasciare una strada per riprovare, non sparire in silenzio.
  it("un rientro in lista che fallisce lo dice accanto alla voce, e si può riprovare", async () => {
    let tentativi = 0;
    stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
      if (init?.method === "POST") {
        tentativi += 1;
        return tentativi === 1 ? [{ detail: "no" }, 500] : [{ added: true }, 200];
      }
      return [ITEMS, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "0" } });
    fireEvent.pointerUp(cursore);
    await userEvent.click(await screen.findByRole("button", { name: "Sì" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/non sono riuscito a rimettere/i);
    // la domanda torna, e il secondo tentativo va a buon fine
    await userEvent.click(await screen.findByRole("button", { name: "Sì" }));
    expect(await screen.findByText("Rimesso in lista.")).toBeDefined();
  });

  // due voci portate a zero in sequenza: la domanda è uno stato per riga, e non
  // deve calpestarsi come faceva `removedId` (un solo id) prima della revisione
  // del Task 5. Qui le voci sono due ingredienti diversi (mela e Total 0%): ogni
  // riga tiene la sua domanda, e rispondere sull'una non deve toccare l'altra.
  it("due voci portate a zero in sequenza non si calpestano: ognuna ha la sua domanda", async () => {
    const fetchMock = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        if (path.includes("/p3")) return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
        if (path.includes("/p1")) return [{ ...ITEMS[0], status: "finished", fill_percent: 0 }, 200];
      }
      if (init?.method === "POST") return [{ added: true }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    // A: la mela a zero
    const cursoreMela = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursoreMela, { target: { value: "0" } });
    fireEvent.pointerUp(cursoreMela);
    await screen.findByText("Lo rimetto in lista?");

    // B: Total 0% a zero, prima di aver risposto per la mela
    const cursoreTotal = await screen.findByRole("slider", { name: "Quanto ne resta di Total 0%" });
    fireEvent.change(cursoreTotal, { target: { value: "0" } });
    fireEvent.pointerUp(cursoreTotal);

    // le due domande convivono
    await waitFor(() => expect(screen.getAllByText("Lo rimetto in lista?")).toHaveLength(2));

    // rispondere no per la mela non tocca la domanda di Total 0%
    const melaRow = screen.getByText("mela").closest("li")!;
    await userEvent.click(within(melaRow).getByRole("button", { name: "No" }));

    await waitFor(() => expect(screen.getAllByText("Lo rimetto in lista?")).toHaveLength(1));
    const totalRow = screen.getByText("Total 0%").closest("li")!;
    expect(within(totalRow).getByText("Lo rimetto in lista?")).toBeDefined();

    // e rispondere sì per Total 0% scrive solo per quella voce
    await userEvent.click(within(totalRow).getByRole("button", { name: "Sì" }));
    const post = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "POST");
    expect(String(post![0])).toContain("/pantry/p1/restock");
  });

  // Rilievo 1 di revisione sul Task 11: `PantryRow` non si smonta quando `removed`
  // diventa vero (stessa chiave, stesso fiber), quindi lo stato locale `asking`
  // sopravvive sotto la lapide. Il difetto non è fra due righe diverse — è fra due
  // rami della stessa riga: archiviare mentre la domanda è a video, e poi annullare,
  // deve non far ricomparire la domanda da sola.
  it("annullare un'archiviazione non fa ricomparire da sola la domanda del rientro in lista", async () => {
    let finished = false;
    let archived = false;
    stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") {
        const body = JSON.parse(String(init!.body));
        if ("fill_percent" in body) {
          finished = true;
          return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
        }
        archived = body.archived;
        return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
      }
      const list = ITEMS.map((item) =>
        item.id === "p3" && finished ? { ...item, status: "finished", fill_percent: 0 } : item
      );
      return [archived ? list.filter((item) => item.id !== "p3") : list, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "0" } });
    fireEvent.pointerUp(cursore);
    await screen.findByText("Lo rimetto in lista?");

    // la domanda resta a video, ma «Togli dalla dispensa» resta cliccabile: non è
    // disabilitato dalla domanda, ed è proprio questo il percorso del rilievo
    await userEvent.click(screen.getByRole("button", { name: "Togli mela dalla dispensa" }));
    await screen.findByText("Tolta dalla dispensa");

    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));

    await waitFor(() => expect(screen.queryByText("Tolta dalla dispensa")).toBeNull());
    // la riga è tornata normale: la domanda non deve essere tornata da sola
    expect(screen.queryByText("Lo rimetto in lista?")).toBeNull();
  });

  // Rilievo 2 di revisione sul Task 11: `change`, `archive` e `undo` passano
  // tutte da `busyId` e disabilitano il loro controllo mentre sono in volo; il
  // restock no, e la domanda si chiudeva da sé appena cliccato «Sì», prima
  // ancora che la richiesta partisse davvero — cioè non c'era mai un istante in
  // cui un secondo clic potesse trovare un bottone disabilitato. Ora la domanda
  // resta a video mentre `restock` è in volo, e «Sì»/«No» sono `disabled`
  // esattamente come lo sono il cursore e la X per le altre mutazioni della riga.
  it("mentre il rientro in lista è in volo la domanda resta a video con «Sì» e «No» disabilitati", async () => {
    const spy = vi.fn((_url: unknown, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return Promise.resolve(
          new Response(JSON.stringify({ ...ITEMS[2], status: "finished", fill_percent: 0 }), { status: 200 })
        );
      }
      if (init?.method === "POST") return new Promise<Response>(() => {}); // mai risolta: si resta "in volo"
      return Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "0" } });
    fireEvent.pointerUp(cursore);
    await userEvent.click(await screen.findByRole("button", { name: "Sì" }));

    // la richiesta non risponde mai: la domanda deve restare a video (non sparire
    // in anticipo sull'esito) e i suoi bottoni devono restare bloccati per tutto
    // il tempo in cui quel tentativo è ancora in volo
    expect(await screen.findByText("Lo rimetto in lista?")).toBeDefined();
    await waitFor(() => expect(screen.getByRole("button", { name: "Sì" })).toBeDisabled());
    expect(screen.getByRole("button", { name: "No" })).toBeDisabled();
  });

  // Rilievo della revisione finale: `busyId` era un valore solo per tutto lo
  // schermo, scelto per priorità fra le mutazioni. Con la PATCH del cursore
  // della riga A in volo vinceva sempre A, e il «Sì» della riga B restava
  // premibile anche mentre il suo POST di restock era in corso — POST che non è
  // idempotente e che `shopping_list_items`, senza vincolo unico, non rimedia.
  it("una mutazione su un'altra riga non sblocca il «Sì» di questa", async () => {
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      const path = String(url);
      // il cursore della mela risponde: serve solo a far comparire la domanda
      if (init?.method === "PATCH" && path.includes("/p3")) {
        return Promise.resolve(
          new Response(JSON.stringify({ ...ITEMS[2], status: "finished", fill_percent: 0 }), { status: 200 })
        );
      }
      // il cursore di Total 0% resta in volo per sempre: è l'altra riga occupata
      if (init?.method === "PATCH") return new Promise<Response>(() => {});
      if (init?.method === "POST") return new Promise<Response>(() => {});
      return Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();

    const mela = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(mela, { target: { value: "0" } });
    fireEvent.pointerUp(mela);
    await screen.findByText("Lo rimetto in lista?");

    // riga A: una PATCH che non risponde mai
    const altra = screen.getByRole("slider", { name: "Quanto ne resta di Total 0%" });
    fireEvent.change(altra, { target: { value: "50" } });
    fireEvent.pointerUp(altra);
    await waitFor(() =>
      expect(screen.getByRole("slider", { name: "Quanto ne resta di Total 0%" })).toBeDisabled()
    );

    // riga B: il «Sì» parte, e da quel momento non deve più essere premibile
    const si = screen.getByRole("button", { name: "Sì" });
    await userEvent.click(si);
    await waitFor(() => expect(screen.getByRole("button", { name: "Sì" })).toBeDisabled());
    await userEvent.click(screen.getByRole("button", { name: "Sì" }));

    const posts = spy.mock.calls.filter(([, init]) => (init as RequestInit)?.method === "POST");
    expect(posts).toHaveLength(1);
  });
});
