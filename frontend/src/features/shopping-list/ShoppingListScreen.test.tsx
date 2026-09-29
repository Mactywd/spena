import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ShoppingListScreen } from "./ShoppingListScreen";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { ShoppingItem } from "../../domain/types";

function item(over: Partial<ShoppingItem> & Pick<ShoppingItem, "id" | "raw_text">): ShoppingItem {
  return {
    ingredient_id: null, ingredient_name: null, ingredient_category: null, ingredient_kind: null,
    status: "pending", reason: "manual", created_at: "2026-09-28T10:00:00Z", ...over,
  };
}

const ITEMS: ShoppingItem[] = [
  item({ id: "s4", raw_text: "zucchine", ingredient_id: "i4", ingredient_name: "zucchina",
    ingredient_category: "verdura", status: "checked" }),
  item({ id: "s1", raw_text: "pomodoro", ingredient_id: "i1", ingredient_name: "pomodoro",
    ingredient_category: "verdura" }),
  item({ id: "s2", raw_text: "Total 0%", ingredient_id: "i2", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", reason: "finished_while_cooking" }),
  item({ id: "s3", raw_text: "cosa verde", status: "checked" }),
];

type Route = (path: string, init?: RequestInit) => [unknown, number];

/** Un fetch che risponde in base a metodo e percorso, e tiene le chiamate. */
function stubRoutedFetch(route: Route) {
  const spy = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const [body, status] = route(String(input), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

const patchesOf = (spy: ReturnType<typeof stubRoutedFetch>) =>
  spy.mock.calls
    .filter(([, init]) => init?.method === "PATCH")
    .map(([url, init]) => [String(url).match(/\/shopping-list\/[^/?]+$/)?.[0], JSON.parse(String(init?.body))]);

// senza `NoticeProvider` l'avviso di conferma (la ✕, «Era già in lista.») non avrebbe
// dove comparire: `useNotice()` restituirebbe il no-op del contesto vuoto
function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <NoticeProvider>
          <ShoppingListScreen />
        </NoticeProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

/** Le caselle di una sezione, nell'ordine in cui si vedono. */
async function boxesIn(heading: string) {
  const section = (await screen.findByRole("heading", { name: heading })).closest("section")!;
  return within(section).getAllByRole("checkbox").map((box) => box.getAttribute("aria-label"));
}

describe("ShoppingListScreen", () => {
  it("una sezione per reparto, con il conteggio; quello ignoto in fondo", async () => {
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    await screen.findByRole("heading", { name: "Verdura" });
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(["Latticini", "Verdura", "Senza reparto"]);
    const verdura = screen.getByRole("heading", { name: "Verdura" }).closest("section")!;
    expect(within(verdura).getByText("2")).toBeDefined();
  });

  it("le voci nel carrello vanno in fondo al loro reparto (dal giro)", async () => {
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    // «zucchine» arriva per prima dal server, ma è nel carrello
    expect(await boxesIn("Verdura")).toEqual(["pomodoro", "zucchina"]);
  });

  it("segnala le voci rientrate dopo aver cucinato", async () => {
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    expect(await screen.findByText("rientrata perché finita cucinando")).toBeDefined();
  });

  it("mostra le voci non abbinate col testo che hai scritto", async () => {
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    expect(await screen.findByText("cosa verde")).toBeDefined();
  });

  it("la scheda d'ingresso conta quel che è nel carrello", async () => {
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    expect(await screen.findByText("2 nel carrello")).toBeDefined();
  });

  it("spuntando una voce la manda nel carrello", async () => {
    const spy = stubRoutedFetch((_path, init) =>
      init?.method === "PATCH" ? [{ ...ITEMS[1], status: "checked" }, 200] : [ITEMS, 200]
    );
    renderScreen();
    await userEvent.click(await screen.findByRole("checkbox", { name: "pomodoro" }));
    await waitFor(() => expect(patchesOf(spy)).toEqual([["/shopping-list/s1", { status: "checked" }]]));
  });

  it("la ✕ toglie la voce e l'avviso offre «Annulla», che la rimette da comprare", async () => {
    const spy = stubRoutedFetch((_path, init) => (init?.method === "PATCH" ? [ITEMS[1], 200] : [ITEMS, 200]));
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli pomodoro dalla lista" }));
    expect(await screen.findByText("Tolto dalla lista: pomodoro")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    await waitFor(() =>
      expect(patchesOf(spy)).toEqual([
        ["/shopping-list/s1", { status: "archived" }],
        ["/shopping-list/s1", { status: "pending" }],
      ])
    );
  });

  it("«Annulla» rimette nel carrello una voce che era nel carrello", async () => {
    const spy = stubRoutedFetch((_path, init) => (init?.method === "PATCH" ? [ITEMS[0], 200] : [ITEMS, 200]));
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli zucchine dalla lista" }));
    fireEvent.click(await screen.findByRole("button", { name: "Annulla" }));
    await waitFor(() =>
      expect(patchesOf(spy)).toEqual([
        ["/shopping-list/s4", { status: "archived" }],
        ["/shopping-list/s4", { status: "checked" }],
      ])
    );
  });

  it("un «Annulla» fallito lo dice, e offre di riprovare", async () => {
    let patches = 0;
    stubRoutedFetch((_path, init) => {
      if (init?.method !== "PATCH") return [ITEMS, 200];
      patches += 1;
      return patches === 1 ? [ITEMS[1], 200] : [{ detail: "no" }, 500];
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli pomodoro dalla lista" }));
    fireEvent.click(await screen.findByRole("button", { name: "Annulla" }));
    expect(await screen.findByText("Non sono riuscito a rimettere pomodoro in lista.")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Riprova" }));
    await waitFor(() => expect(patches).toBe(3));
  });

  it("se nel frattempo la stessa cosa è tornata in lista, «Annulla» non fa il doppione", async () => {
    // dopo la ✕ il server risponde con la voce tolta sparita e un «pomodoro» nuovo,
    // riscritto dalla barra: stesso ingrediente, altra voce
    let archived = false;
    const rewritten = item({ id: "s9", raw_text: "pomodori", ingredient_id: "i1",
      ingredient_name: "pomodoro", ingredient_category: "verdura" });
    const spy = stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") {
        archived = true;
        return [ITEMS[1], 200];
      }
      return [archived ? [...ITEMS.filter((i) => i.id !== "s1"), rewritten] : ITEMS, 200];
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli pomodoro dalla lista" }));
    await screen.findByText("pomodori");
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(await screen.findByText("Era già in lista.")).toBeDefined();
    expect(patchesOf(spy)).toEqual([["/shopping-list/s1", { status: "archived" }]]);
  });

  it("se la cache non lo sa ma il server sì, «Annulla» dice «Era già in lista.» e non offre «Riprova»", async () => {
    // La POST della barra e il refetch si sono incrociati: la cache non ha ancora la voce
    // riscritta, quindi la PATCH parte, e il server risponde 409 (la difesa vera). Non è
    // un guasto: riprovare rifallirebbe
    let patches = 0;
    const spy = stubRoutedFetch((_path, init) => {
      if (init?.method !== "PATCH") return [patches === 0 ? ITEMS : ITEMS.filter((i) => i.id !== "s1"), 200];
      patches += 1;
      return patches === 1 ? [ITEMS[1], 200] : [{ detail: "l'ingrediente è già in lista" }, 409];
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli pomodoro dalla lista" }));
    await screen.findByText("Tolto dalla lista: pomodoro");
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(await screen.findByText("Era già in lista.")).toBeDefined();
    expect(screen.queryByText("Non sono riuscito a rimettere pomodoro in lista.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
    expect(patchesOf(spy)).toEqual([
      ["/shopping-list/s1", { status: "archived" }],
      ["/shopping-list/s1", { status: "pending" }],
    ]);
  });

  it("la riga resta bloccata finché il riordino dopo la ✕ non è arrivato (regressione)", async () => {
    // la PATCH torna subito, ma il GET che `invalidate()` lancia in `onSuccess` resta
    // appeso finché non lo sblocchiamo: se `onSuccess` non ne aspetta la promise, React
    // Query lascia `isPending` prima che il riordino sia arrivato, e la riga si sblocca
    // con la voce ancora a video
    let releaseGet: (response: Response) => void = () => {};
    let getCalls = 0;
    const spy = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return Promise.resolve(new Response(JSON.stringify(ITEMS[1]), { status: 200 }));
      }
      getCalls += 1;
      if (getCalls === 1) return Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }));
      return new Promise<Response>((resolve) => { releaseGet = resolve; });
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli pomodoro dalla lista" }));
    await screen.findByText("Tolto dalla lista: pomodoro");
    // la PATCH è tornata (l'avviso lo prova), ma il refetch è ancora appeso: la riga
    // deve restare bloccata
    const box = screen.getByRole("checkbox", { name: "pomodoro" });
    expect(box).toHaveAttribute("aria-disabled", "true");
    const remove = screen.getByRole("button", { name: "Togli pomodoro dalla lista" });
    expect(remove).toHaveAttribute("aria-disabled", "true");
    // `await act` dopo ogni tocco: `mutate` chiama `mutationFn` solo dopo `onMutate` (TanStack
    // Query 5), quindi senza aspettare il microtask l'asserzione sotto passerebbe anche con
    // la guardia disattivata — non avrebbe ancora visto la seconda `fetch`.
    fireEvent.click(box);
    await act(async () => {});
    fireEvent.click(remove);
    await act(async () => {});
    expect(spy.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
    releaseGet(new Response(JSON.stringify(ITEMS.filter((i) => i.id !== "s1")), { status: 200 }));
    await waitFor(() => expect(screen.queryByText("pomodoro")).toBeNull());
  });

  it("una modifica rifiutata lo dice accanto alla voce giusta, e la voce resta", async () => {
    stubRoutedFetch((_path, init) => (init?.method === "PATCH" ? [{ detail: "no" }, 500] : [ITEMS, 200]));
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli pomodoro dalla lista" }));
    const alert = await screen.findByRole("alert");
    expect(alert.closest("li")).toBe(screen.getByRole("checkbox", { name: "pomodoro" }).closest("li"));
    expect(screen.queryByText("Tolto dalla lista: pomodoro")).toBeNull();
  });

  it("mentre una scrittura è in volo, la stessa voce non ne parte una seconda", async () => {
    let release: (response: Response) => void = () => {};
    const spy = vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === "PATCH"
        ? new Promise<Response>((resolve) => { release = resolve; })
        : Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);
    renderScreen();
    const box = await screen.findByRole("checkbox", { name: "pomodoro" });
    fireEvent.click(box);
    await waitFor(() => expect(box).toHaveAttribute("aria-disabled", "true"));
    // `await act` dopo ogni tocco: vedi il commento sull'altro test di questo file
    fireEvent.click(box);
    await act(async () => {});
    const remove = screen.getByRole("button", { name: "Togli pomodoro dalla lista" });
    expect(remove).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(remove);
    await act(async () => {});
    expect(spy.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
    release(new Response(JSON.stringify({ ...ITEMS[1], status: "checked" }), { status: 200 }));
  });

  it("un ingrediente già in lista non si doppia: «Era già in lista.» nell'avviso", async () => {
    const spy = stubRoutedFetch((path, init) =>
      init?.method === "POST"
        ? [{ ...ITEMS[1], added: false }, 200]
        : path.includes("/ingredients") // i suggerimenti della barra: nessuno
          ? [[], 200]
          : [ITEMS, 200]
    );
    renderScreen();
    await screen.findByText("pomodoro");
    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomodoro{Enter}");
    expect(await screen.findByText("Era già in lista.")).toBeDefined();
    // guarda il filo barra reale → schermo → POST (S18): il testo va com'è, a
    // riconoscerlo è il backend, non il campo
    const post = spy.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ raw_text: "pomodoro", ingredient_id: null });
  });

  it("una lista vuota lo dice, e dice cosa fare", async () => {
    stubRoutedFetch(() => [[], 200]);
    renderScreen();
    expect(await screen.findByRole("heading", { name: "Lista vuota" })).toBeDefined();
    expect(screen.getByText("Niente nel carrello, per ora")).toBeDefined();
  });

  it("un caricamento fallito non viene spacciato per lista vuota, e si può riprovare", async () => {
    let calls = 0;
    stubRoutedFetch((_path, init) => {
      if (init?.method) return [{}, 200];
      calls += 1;
      return calls === 1 ? [{ detail: "no" }, 500] : [ITEMS, 200];
    });
    renderScreen();
    expect(await screen.findByText(/Non sono riuscito a caricare la lista/)).toBeDefined();
    expect(screen.queryByRole("heading", { name: "Lista vuota" })).toBeNull();
    // né la scheda d'ingresso afferma qualcosa sul contenuto
    expect(screen.getByText("Metti via quello che hai comprato")).toBeDefined();
    // e scrivere resta possibile
    expect(screen.getByLabelText("Aggiungi alla lista")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("pomodoro")).toBeDefined();
  });
});
