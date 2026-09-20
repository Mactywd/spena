import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { RecipeDetailScreen } from "./RecipeDetailScreen";
import type { PantryItem } from "../../domain/types";

const DETAIL = {
  id: "r1", title: "Pasta al pomodoro", description: "Di sempre", source: "manual",
  missing: 2, cookable: false, image_url: null as string | null, instructions: "Cuoci.",
  servings: 2 as number | null, source_ref: null, scaled_to: null as number | null,
  unscalable_lines: 0,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "180 g",
      quantity_display: "180 g", quantity_scaled: false,
      note: null, availability: "available", satisfied: true },
    { ingredient_id: "i2", ingredient_name: "pomodoro", role: "primary", quantity_text: "400 g",
      quantity_display: "400 g", quantity_scaled: false,
      note: null, availability: "low", satisfied: false },
    { ingredient_id: "i3", ingredient_name: "aglio", role: "secondary", quantity_text: null,
      quantity_display: null, quantity_scaled: false,
      note: null, availability: "low", satisfied: true },
    // senza una riga che manca, metà di statusNote non è coperta da niente
    { ingredient_id: "i4", ingredient_name: "basilico", role: "secondary", quantity_text: null,
      quantity_display: null, quantity_scaled: false,
      note: null, availability: "missing", satisfied: false },
  ],
};

const PANTRY: PantryItem[] = [
  { id: "p1", ingredient_id: "i1", product_id: null, ingredient_name: "pasta",
    ingredient_category: "cereali", product_name: null, product_brand: null,
    status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z" },
  { id: "p2", ingredient_id: "i2", product_id: "pr1", ingredient_name: "pomodoro",
    ingredient_category: "conserve", product_name: "Pelati", product_brand: "Mutti",
    status: "low", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z" },
];

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/ricette/r1"]}>
        <Routes>
          <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

/** Lo stesso dettaglio del file, con una provenienza diversa.
 *
 * `mockImplementation` e non `mockResolvedValue`: la schermata fa più di una
 * chiamata, e il corpo di una Response si legge una volta sola. */
function stubFetchWithSourceRef(sourceRef: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ ...DETAIL, source: "dataset", source_ref: sourceRef }), {
          status: 200,
        })
      )
    )
  );
}

/** Lo stesso dettaglio del file, con delle proprietà sostituite.
 *
 * `mockImplementation` e non `mockResolvedValue`: la schermata fa più di una
 * chiamata, e il corpo di una Response si legge una volta sola. */
function stubFetch(overrides: Partial<typeof DETAIL>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ ...DETAIL, ...overrides }), { status: 200 })
      )
    )
  );
}

describe("RecipeDetailScreen", () => {
  it("distingue ingredienti principali e secondari", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("Principali")).toBeDefined();
    expect(screen.getByText("Secondari")).toBeDefined();
  });

  it("spiega perché un principale quasi finito non basta", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    const row = (await screen.findByText("pomodoro")).closest("li")!;
    expect(row.textContent).toContain("quasi finito, non basta");
  });

  it("un secondario quasi finito è accettato", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    const row = (await screen.findByText("aglio")).closest("li")!;
    expect(row.textContent).toContain("quasi finito, basta");
  });

  it("l'ordine delle righe è quello del backend: niente qui le riordina", async () => {
    // quantity_text è testo da mostrare: non entra in un ordinamento, in un
    // confronto né in un calcolo. L'ordine è quello che ha deciso il server.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    const principali = (await screen.findByText("Principali")).closest("section")!;
    expect(
      within(principali)
        .getAllByRole("listitem")
        .map((row) => row.textContent)
    ).toEqual(["pasta180 gdisponibile", "pomodoro400 gquasi finito, non basta"]);
  });

  it("dice cosa manca e cosa c'è, non solo i casi a metà", async () => {
    // Scambiare "manca" e "disponibile" è l'output più fuorviante possibile di
    // questo schermo: l'utente va a fare la spesa per qualcosa che ha, e cucina
    // credendo di avere qualcosa che non ha.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    const assente = (await screen.findByText("basilico")).closest("li")!;
    expect(assente.textContent).toContain("manca");

    const presente = screen.getByText("pasta").closest("li")!;
    expect(presente.textContent).toContain("disponibile");
  });

  it("una cottura riuscita dice quanto è tornato in lista, col numero del backend", async () => {
    // È l'output del gesto per cui esiste tutto il task: chi dichiara finito un
    // vasetto deve sapere che è tornato in lista. Il numero arriva dal server —
    // qui ne dichiariamo uno solo e il backend ne risponde due, perché contarli
    // da questa parte sarebbe una supposizione.
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown, init?: RequestInit) => {
        if (String(url).includes("/cook")) {
          return Promise.resolve(
            new Response(JSON.stringify({ event_id: "e1", updated: 1, restocked: 2 }), {
              status: 201,
            })
          );
        }
        if (String(url).includes("/pantry")) {
          return Promise.resolve(new Response(JSON.stringify(PANTRY), { status: 200 }));
        }
        expect(init?.method ?? "GET").toBe("GET");
        return Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }));
      })
    );

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: "Cucina" }));
    const row = (await screen.findByText("Pelati")).closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Finito" }));
    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Segnato. 2 cose sono tornate in lista della spesa."
    );
  });

  it("un fallimento nel caricare la ricetta lo dice, non resta a caricare per sempre", async () => {
    // Confondere "carico" con "fallito" lascerebbe lo schermo bloccato su "Carico…"
    // in eterno: l'utente non saprebbe mai che non arriverà nulla.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));
    renderScreen();
    expect(await screen.findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
  });

  it("un fallimento nel caricare la dispensa non apre un foglio di cottura vuoto e muto", async () => {
    // "Cucina" apre CookSheet con le voci di dispensa: se la dispensa non si è
    // caricata, offrire comunque il pulsante produrrebbe un foglio che sembra
    // completo ma non lo è, l'errore travestito da "niente da aggiornare".
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) => {
        if (String(url).includes("/pantry")) {
          return Promise.resolve(new Response("", { status: 500 }));
        }
        return Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }));
      })
    );
    renderScreen();
    expect(await screen.findByText("Principali")).toBeDefined();
    expect(await screen.findByRole("alert")).toHaveTextContent(/dispensa/i);
    expect(screen.queryByRole("button", { name: "Cucina" })).toBeNull();
  });

  it("offre l'originale quando la ricetta viene da un indirizzo", async () => {
    stubFetchWithSourceRef("https://ricette.giallozafferano.it/Tiramisu.html");
    renderScreen();

    const link = await screen.findByRole("link", { name: /originale/i });
    expect(link).toHaveAttribute("href", "https://ricette.giallozafferano.it/Tiramisu.html");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
  });

  it("non offre niente quando la provenienza non è un indirizzo", async () => {
    stubFetchWithSourceRef("seme iniziale");
    renderScreen();

    expect(await screen.findByText("Pasta al pomodoro")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /originale/i })).not.toBeInTheDocument();
  });

  it("da una ricetta aperta si torna al ricettario con un tasto", async () => {
    // in una PWA su iOS il tasto indietro del telefono non c'è: senza questo
    // collegamento l'unica uscita è la barra in basso
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    expect((await screen.findByRole("link", { name: "Ricette" })).getAttribute("href"))
      .toBe("/ricette");
  });

  it("la ricetta aperta mostra la sua foto", async () => {
    // fino a ieri si vedeva solo nell'elenco: aprire la ricetta la faceva sparire
    stubFetch({ image_url: "https://esempio.invalid/foto.jpg" });
    renderScreen();
    expect((await screen.findByRole("img", { name: "Pasta al pomodoro" })).getAttribute("src"))
      .toBe("https://esempio.invalid/foto.jpg");
  });

  it("una foto che non carica non lascia un buco sopra il titolo", async () => {
    stubFetch({ image_url: "https://esempio.invalid/rotta.jpg" });
    renderScreen();
    fireEvent.error(await screen.findByRole("img", { name: "Pasta al pomodoro" }));
    expect(screen.queryByRole("img", { name: "Pasta al pomodoro" })).toBeNull();
    // il resto della scheda resta al suo posto
    expect(screen.getByRole("heading", { name: "Pasta al pomodoro" })).toBeDefined();
  });

  /** Come `stubFetch`, ma la risposta dipende dall'indirizzo: qui servono due corpi
   * diversi — la ricetta com'è, e la ricetta riporzionata — e `mockImplementation` è
   * obbligatorio perché il corpo di una Response si legge una volta sola. */
  function stubFetchByUrl(route: (url: string) => unknown) {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) =>
        Promise.resolve(new Response(JSON.stringify(route(String(url))), { status: 200 }))
      )
    );
  }

  // la stessa ricetta chiesta per 2 invece che per 4: è il server a decidere queste
  // stringhe, e il client non le ricalcola — per questo il finto le detta
  const DIMEZZATA = {
    ...DETAIL,
    scaled_to: 2,
    unscalable_lines: 2,
    ingredients: [
      { ...DETAIL.ingredients[0], quantity_display: "90 g", quantity_scaled: true },
      { ...DETAIL.ingredients[1], quantity_display: "200 g", quantity_scaled: true },
      { ...DETAIL.ingredients[2], quantity_display: null, quantity_scaled: false },
      { ...DETAIL.ingredients[3], quantity_display: null, quantity_scaled: false },
    ],
  };

  it("il selettore delle porzioni rilegge la ricetta e mostra quel che dice il server", async () => {
    // il client non fa aritmetica: chiede e mostra. È la riga di CLAUDE.md che tiene
    // in piedi la porta a Capacitor.
    const spy = vi.fn();
    stubFetchByUrl((url) => {
      spy(url);
      return url.includes("servings=1") ? DIMEZZATA : DETAIL;
    });

    renderScreen();
    expect(await screen.findByText("180 g")).toBeDefined();

    // DETAIL è per 2 porzioni: un tocco porta a 1
    await userEvent.click(screen.getByRole("button", { name: "Una porzione in meno" }));

    expect(await screen.findByText("90 g")).toBeDefined();
    // e la copertura si dichiara invece di far finta di niente
    expect(screen.getByText(/2 dosi su 4 non si riscalano/)).toBeDefined();
    expect(spy.mock.calls.some(([url]) => String(url).includes("servings=1"))).toBe(true);
  });

  it("senza porzioni dichiarate il selettore non compare", async () => {
    stubFetch({ servings: null });
    renderScreen();
    await screen.findByText("180 g");
    expect(screen.queryByRole("button", { name: /porzione in meno/ })).toBeNull();
  });
});
