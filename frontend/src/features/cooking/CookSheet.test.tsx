import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CookSheet } from "./CookSheet";
import type { PantryItem, RecipeDetail } from "../../domain/types";

const RECIPE: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: null, source: "manual",
  missing: 0, cookable: true, instructions: "Cuoci.", servings: 2, source_ref: null,
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
    status: "available", note: null, added_at: "2026-09-11T10:00:00Z" },
  { id: "p2", ingredient_id: "i2", product_id: "pr1", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Total 0%", product_brand: "Fage",
    status: "available", note: null, added_at: "2026-09-11T10:00:00Z" },
  { id: "p3", ingredient_id: "i2", product_id: "pr2", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Pesca", product_brand: "Carrefour",
    status: "low", note: null, added_at: "2026-09-11T10:00:00Z" },
];

function renderSheet(onDone = vi.fn(), client = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})) {
  const view = render(
    <QueryClientProvider client={client}>
      <CookSheet recipe={RECIPE} pantryItems={PANTRY} onDone={onDone} />
    </QueryClientProvider>
  );
  return { ...view, client };
}

describe("CookSheet", () => {
  it("elenca ogni vasetto separatamente, non l'ingrediente astratto", async () => {
    renderSheet();
    expect(screen.getByText("Total 0%")).toBeDefined();
    expect(screen.getByText("Pesca")).toBeDefined();
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

  it("dichiarare quasi finito non spunta il riacquisto", async () => {
    renderSheet();
    const row = screen.getByText("Total 0%").closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Quasi finito" }));

    expect(within(row).getByRole("checkbox", { name: /Rimetti in lista/ })).not.toBeChecked();
  });

  it("invia le transizioni scelte e chiama onDone", async () => {
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
    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());
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
