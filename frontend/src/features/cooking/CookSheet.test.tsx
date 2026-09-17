import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CookSheet } from "./CookSheet";
import type { PantryItem, RecipeDetail } from "../../domain/types";

const RECIPE: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: null, source: "manual",
  missing: 0, cookable: true, image_url: null, prep_minutes: null, cook_minutes: null,
  category: null, instructions: "Cuoci.", servings: 2, source_ref: null,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "180 g",
      note: null, availability: "available", satisfied: true },
    { ingredient_id: "i2", ingredient_name: "yogurt greco", role: "secondary",
      quantity_text: "q.b.", note: null, availability: "available", satisfied: true },
  ],
};

const PANTRY: PantryItem[] = [
  { id: "p1", ingredient_id: "i1", product_id: null, ingredient_name: "pasta",
    ingredient_category: "cereali", product_name: null, product_brand: null,
    status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z" },
  { id: "p2", ingredient_id: "i2", product_id: "pr1", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Total 0%", product_brand: "Fage",
    status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z" },
  { id: "p3", ingredient_id: "i2", product_id: "pr2", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Pesca", product_brand: "Carrefour",
    status: "low", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z" },
  // un secondo sacco di pasta senza codice a barre, quello che "sistema la spesa"
  // produce di routine: non ha né prodotto né marca, e si distingue dal primo solo
  // per la nota, lo stato e la data d'ingresso
  { id: "p4", ingredient_id: "i1", product_id: null, ingredient_name: "pasta",
    ingredient_category: "cereali", product_name: null, product_brand: null,
    status: "low", fill_percent: null, note: "quella aperta", added_at: "2026-09-01T10:00:00Z" },
  // già finita e mai archiviata: GET /pantry la restituisce ancora
  { id: "p5", ingredient_id: "i2", product_id: "pr3", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Greco 2%", product_brand: "Lidl",
    status: "finished", fill_percent: null, note: null, added_at: "2026-09-10T10:00:00Z" },
];

function renderSheet(
  onDone = vi.fn(),
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  items: PantryItem[] = PANTRY
) {
  const sheet = (next: PantryItem[]) => (
    <QueryClientProvider client={client}>
      <CookSheet recipe={RECIPE} pantryItems={next} onDone={onDone} />
    </QueryClientProvider>
  );
  const view = render(sheet(items));
  // la dispensa è una prop viva: la query si aggiorna anche a foglio aperto
  return { ...view, client, onDone, show: (next: PantryItem[]) => view.rerender(sheet(next)) };
}

describe("CookSheet", () => {
  it("elenca ogni vasetto separatamente, non l'ingrediente astratto", async () => {
    renderSheet();
    expect(screen.getByText("Total 0%")).toBeDefined();
    expect(screen.getByText("Pesca")).toBeDefined();
  });

  it("ogni riga porta marca, nota e stato attuale, non il solo nome", async () => {
    // Due confezioni dello stesso ingrediente devono essere distinguibili a
    // colpo d'occhio: chi dichiara "finito" sul vasetto sbagliato lascia quello
    // vero disponibile, la ricetta continua a dirsi cucinabile e niente torna in
    // lista. Lo stato attuale serve anche a dare un referente a "Invariato".
    renderSheet();
    const yogurt = screen.getByText("Total 0%").closest("li")!;
    expect(yogurt.textContent).toContain("Fage");
    expect(yogurt.textContent).toContain("Disponibile");

    const pesca = screen.getByText("Pesca").closest("li")!;
    expect(pesca.textContent).toContain("Carrefour");
    expect(pesca.textContent).toContain("Quasi finito");

    const aperta = screen.getByText("quella aperta").closest("li")!;
    expect(aperta.textContent).toContain("pasta");
  });

  it("due confezioni identiche tranne la data d'ingresso restano distinguibili", async () => {
    // Il caso peggiore e più comune: due sacchi di pasta senza prodotto, senza
    // marca, senza nota e nello stesso stato. Resta solo da quando sono in
    // dispensa, e deve comparire sia nella riga sia nel nome del controllo.
    const bag = (id: string, addedAt: string): PantryItem => ({
      id, ingredient_id: "i1", product_id: null, ingredient_name: "pasta",
      ingredient_category: "cereali", product_name: null, product_brand: null,
      status: "available", fill_percent: null, note: null, added_at: addedAt,
    });
    renderSheet(vi.fn(), undefined, [
      bag("pa", "2026-09-11T10:00:00Z"),
      bag("pb", "2026-09-01T10:00:00Z"),
    ]);

    const [first, second] = screen.getAllByRole("listitem");
    expect(first.textContent).not.toBe(second.textContent);

    await userEvent.click(within(first).getByRole("button", { name: "Finito" }));
    await userEvent.click(within(second).getByRole("button", { name: "Finito" }));
    const [firstBox, secondBox] = screen.getAllByRole("checkbox");
    expect(firstBox.getAttribute("aria-label")).not.toBe(secondBox.getAttribute("aria-label"));
  });

  it("una confezione già finita non compare: non c'è niente da dichiarare", async () => {
    // GET /pantry restituisce anche le voci finite finché non vengono archiviate:
    // elencarle qui seppellisce l'unico vasetto vero in mezzo a quelli vuoti.
    renderSheet();
    expect(screen.queryByText("Greco 2%")).toBeNull();
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
  });

  it("non invia nulla per le voci lasciate invariate", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 0, restocked: 0 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    renderSheet();
    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

    const body = JSON.parse(spy.mock.calls[0][1].body);
    expect(body.transitions).toEqual([]);
  });

  it("dichiarare finito un prodotto propone il riacquisto, già spuntato", async () => {
    renderSheet();
    const row = screen.getByText("Total 0%").closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Finito" }));

    expect(within(row).getByRole("checkbox", { name: /Rimetti in lista/ })).toBeChecked();
  });

  it("dichiarare quasi finito manda 'low' e non spunta il riacquisto", async () => {
    // "low" è l'unico segnale che fa funzionare la regola primario/secondario:
    // scriverlo come "available" cancellerebbe la differenza fra un barattolo
    // quasi vuoto che basta per un soffritto e uno pieno. Va verificato sul
    // payload, non sulla casella: la casella non dice cosa arriva al server.
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 1, restocked: 0 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    renderSheet();
    const row = screen.getByText("Total 0%").closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Quasi finito" }));

    expect(within(row).getByRole("checkbox", { name: /Rimetti in lista/ })).not.toBeChecked();

    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));
    const body = JSON.parse(spy.mock.calls[0][1].body);
    expect(body.transitions).toEqual([
      { pantry_item_id: "p2", to_status: "low", restock: false },
    ]);
  });

  it("invia le transizioni scelte e passa l'esito del backend a onDone", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 1, restocked: 1 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);
    const onDone = vi.fn();

    renderSheet(onDone);
    const row = screen.getByText("Total 0%").closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Finito" }));
    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

    const body = JSON.parse(spy.mock.calls[0][1].body);
    expect(body.transitions).toEqual([
      { pantry_item_id: "p2", to_status: "finished", restock: true },
    ]);
    // l'esito serve sopra: questo foglio sta per smontarsi, e senza passarlo il
    // gesto non dice mai che cosa è tornato in lista
    await vi.waitFor(() =>
      expect(onDone).toHaveBeenCalledWith({ event_id: "e1", updated: 1, restocked: 1 })
    );
  });

  it("una voce sparita dalla dispensa a foglio aperto non entra nel payload", async () => {
    // Se la voce viene archiviata da un'altra scheda, il suo id non esiste più: il
    // backend rifiuterebbe tutta la cottura per una riga che l'utente non ha più
    // davanti e non può correggere.
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 0, restocked: 0 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    const { show } = renderSheet();
    const row = screen.getByText("Pesca").closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Finito" }));

    show(PANTRY.filter((item) => item.id !== "p3"));
    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

    const body = JSON.parse(spy.mock.calls[0][1].body);
    expect(body.transitions).toEqual([]);
  });

  it("una voce comparsa a foglio aperto non rompe il foglio", async () => {
    const { show } = renderSheet();
    show([
      ...PANTRY,
      { id: "p6", ingredient_id: "i1", product_id: null, ingredient_name: "pasta",
        ingredient_category: "cereali", product_name: "Penne rigate", product_brand: "Barilla",
        status: "available", fill_percent: null, note: null, added_at: "2026-09-12T10:00:00Z" },
    ]);

    const row = screen.getByText("Penne rigate").closest("li")!;
    expect(within(row).getByRole("button", { name: "Invariato" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  it("un foglio senza voci dice perché è vuoto", async () => {
    // Un pannello bianco con un pulsante si legge come un guasto, non come
    // "niente da aggiornare".
    renderSheet(vi.fn(), undefined, []);
    expect(screen.getByText(/Niente di questa ricetta è in dispensa/)).toBeDefined();
    expect(screen.getByRole("button", { name: "Ho cucinato" })).toBeEnabled();
  });

  it("si può uscire dal foglio senza registrare una cottura", async () => {
    const spy = vi.fn();
    vi.stubGlobal("fetch", spy);
    const onDone = vi.fn();

    renderSheet(onDone);
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));

    expect(onDone).toHaveBeenCalledWith();
    expect(spy).not.toHaveBeenCalled();
  });

  it("le tre scelte sono un gruppo con nome, con bersagli da pollice", async () => {
    // Stesso standard di StatusToggle, che è lo stesso controllo uno schermo più
    // in là: da telefono tre pulsanti da 26px sono tre bersagli mancabili, e per
    // chi legge con lo screen reader tre "Finito" senza confezione non dicono nulla.
    renderSheet();
    const row = screen.getByText("Total 0%").closest("li")!;
    const group = within(row).getByRole("group");
    expect(group.getAttribute("aria-label")).toContain("Total 0%");
    expect(group.getAttribute("aria-label")).toContain("Fage");
    for (const button of within(group).getAllByRole("button")) {
      expect(button).toHaveClass("min-h-11");
    }
  });

  it("una cottura riuscita invalida dispensa, lista della spesa e ricette", async () => {
    // Cucinare cambia sia la dispensa (gli stati appena dichiarati) sia la lista
    // della spesa (il riacquisto di ciò che è finito): senza invalidare entrambe,
    // tornando a quegli schermi l'utente non vede quel che è appena successo, e
    // questo romperebbe esattamente il cerchio che il task deve chiudere. Mutando
    // via l'invalidazione della dispensa nel codice, questo test è l'unico a
    // cadere: una prova che aveva denti.
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 1, restocked: 1 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(["pantry"], PANTRY);
    client.setQueryData(["shopping-list"], []);
    client.setQueryData(["recipe", "r1"], RECIPE);
    client.setQueryData(["recipes", "", false], [RECIPE]);

    const { client: used } = renderSheet(vi.fn(), client);
    const row = screen.getByText("Total 0%").closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Finito" }));
    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

    await vi.waitFor(() => {
      expect(used.getQueryState(["pantry"])?.isInvalidated).toBe(true);
    });
    expect(used.getQueryState(["shopping-list"])?.isInvalidated).toBe(true);
    expect(used.getQueryState(["recipe", "r1"])?.isInvalidated).toBe(true);
    expect(used.getQueryState(["recipes", "", false])?.isInvalidated).toBe(true);
  });

  it("una cottura fallita lo dice, senza svuotare le scelte fatte", async () => {
    // Senza questo, un errore di rete sparirebbe in silenzio: l'utente preme "Ho
    // cucinato", non succede nulla di visibile, e non sa se riprovare o se la
    // dispensa sia già stata aggiornata.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));

    renderSheet();
    const row = screen.getByText("Total 0%").closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Finito" }));
    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
    // la scelta fatta prima dell'invio non si è svuotata
    expect(within(row).getByRole("button", { name: "Finito" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  it("si può togliere la spunta al riacquisto di una voce finita", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 1, restocked: 0 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    renderSheet();
    const row = screen.getByText("Total 0%").closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Finito" }));
    await userEvent.click(within(row).getByRole("checkbox", { name: /Rimetti in lista/ }));
    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

    const body = JSON.parse(spy.mock.calls[0][1].body);
    expect(body.transitions[0].restock).toBe(false);
  });
});
