import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { PantryScreen } from "./PantryScreen";

const ITEMS = [
  { id: "p1", ingredient_id: "i1", product_id: "pr1", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Total 0%", product_brand: "Fage",
    status: "available", note: null, added_at: "2026-09-11T10:00:00Z" },
  { id: "p2", ingredient_id: "i1", product_id: "pr2", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Pesca", product_brand: "Carrefour",
    status: "low", note: null, added_at: "2026-09-11T10:00:00Z" },
  { id: "p3", ingredient_id: "i2", product_id: null, ingredient_name: "mela",
    ingredient_category: "frutta", product_name: null, product_brand: null,
    status: "available", note: null, added_at: "2026-09-11T10:00:00Z" },
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

  it("cambiare stato manda una PATCH con il nuovo valore e lo schermo lo rispecchia", async () => {
    // la PATCH risponde con la riga, la GET successiva con la lista aggiornata:
    // distinguerle è ciò che rende il test una copertura del ri-render e non solo
    // della chiamata
    const changed = [{ ...ITEMS[0], status: "low" }, ITEMS[1], ITEMS[2]];
    const spy = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return Promise.resolve(
          new Response(JSON.stringify({ ...ITEMS[0], status: "low" }), { status: 200 })
        );
      }
      const body = spy.mock.calls.some(([, i]) => i?.method === "PATCH") ? changed : ITEMS;
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);

    renderScreen();
    const row = (await screen.findByText("Total 0%")).closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Quasi finito" }));

    const patch = spy.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(patch?.[0]).toContain("/pantry/p1");
    expect(JSON.parse(patch?.[1].body)).toEqual({ status: "low" });

    await waitFor(() => {
      const updated = screen.getByText("Total 0%").closest("li")!;
      expect(within(updated).getByRole("button", { name: "Quasi finito" }))
        .toHaveAttribute("aria-pressed", "true");
    });
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
    await userEvent.click(within(row).getByRole("button", { name: "Quasi finito" }));

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
    await userEvent.click(within(row).getByRole("button", { name: "Quasi finito" }));

    await waitFor(() =>
      expect(within(row).getByRole("button", { name: "Finito" })).toBeDisabled()
    );
    expect(within(row).getByRole("button", { name: "Togli Total 0% dalla dispensa" })).toBeDisabled();
    const other = screen.getByText("Pesca").closest("li")!;
    expect(within(other).getByRole("button", { name: "Finito" })).not.toBeDisabled();
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
});
