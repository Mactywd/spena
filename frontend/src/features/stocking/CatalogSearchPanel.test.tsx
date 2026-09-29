import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CatalogSearchPanel } from "./CatalogSearchPanel";
import type { Product } from "../../domain/types";

const FAGE: Product = {
  id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};
const BURRO: Product = {
  id: "p2", ingredient_id: "i8", ingredient_name: "burro", name: "Burro greco", brand: null,
  barcode: null, source: "custom", nutrients: null, image_url: null,
};
const LATTE: Product = {
  id: "p3", ingredient_id: "i9", ingredient_name: "latte", name: "Latte greco", brand: null,
  barcode: null, source: "custom", nutrients: null, image_url: null,
};

/** La ricerca a catalogo risponde sempre la stessa cosa, o non risponde. */
function stubSearch(found: Product[] | "down") {
  const spy = vi.fn((_url: unknown) =>
    Promise.resolve(
      found === "down"
        ? new Response(JSON.stringify({ detail: "giù" }), { status: 500 })
        : new Response(JSON.stringify(found), { status: 200 })
    )
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderPanel() {
  const props = { onPicked: vi.fn(), onCreateByHand: vi.fn(), onCancel: vi.fn() };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CatalogSearchPanel itemLabel="yogurt greco" ingredientId="i1" {...props} />
    </QueryClientProvider>
  );
  return props;
}

const HINT = /Scrivi il nome o la marca/;

describe("CatalogSearchPanel", () => {
  it("si apre già cercando il nome della voce, e offre i prodotti del suo ingrediente", async () => {
    const spy = stubSearch([FAGE]);
    const { onPicked } = renderPanel();
    await userEvent.click(await screen.findByRole("option", { name: /Total 0% Fage/ }));
    expect(onPicked).toHaveBeenCalledWith(FAGE);
    expect(String(spy.mock.calls[0][0])).toContain("/products/search?q=yogurt%20greco");
    // l'esempio è l'invito di un campo vuoto: accanto ai risultati sembrava una risposta
    expect(screen.queryByText(HINT)).toBeNull();
  });

  it("l'elenco è un listbox di opzioni, senza voci d'elenco in mezzo", async () => {
    stubSearch([FAGE]);
    renderPanel();
    const listbox = await screen.findByRole("listbox", { name: "Prodotti per «yogurt greco»" });
    expect(within(listbox).getByRole("option", { name: /Total 0%/ }).parentElement).toBe(listbox);
    expect(listbox.querySelector("li")).toBeNull();
  });

  it("svuotato il campo compare l'esempio, e nient'altro", async () => {
    stubSearch([FAGE]);
    renderPanel();
    await screen.findByRole("option", { name: /Total 0%/ });
    await userEvent.clear(screen.getByLabelText("Cerca a catalogo"));
    expect(screen.getByText(HINT)).toBeDefined();
    expect(screen.queryByRole("option")).toBeNull();
    expect(screen.queryByText(/Nessun prodotto/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Crea il prodotto a mano" })).toBeNull();
  });

  it("solo prodotti di altri ingredienti: un messaggio solo, che dice quali, e la creazione a mano", async () => {
    stubSearch([BURRO, LATTE]);
    const { onCreateByHand } = renderPanel();
    const note = await screen.findByText(
      /Altri 2 prodotti corrispondono, ma sono di altri ingredienti: burro, latte\./
    );
    // non è un guasto: niente rosso (dal giro)
    expect(note.className).not.toContain("text-danger");
    expect(screen.queryByText(/Nessun prodotto con queste parole/)).toBeNull();
    expect(screen.queryByRole("option")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Crea il prodotto a mano" }));
    expect(onCreateByHand).toHaveBeenCalled();
  });

  it("niente di niente: «nessun prodotto», e non l'altro messaggio", async () => {
    stubSearch([]);
    renderPanel();
    expect(await screen.findByText(/Nessun prodotto con queste parole/)).toBeDefined();
    expect(screen.queryByText(/di un altro ingrediente|di altri ingredienti/)).toBeNull();
    expect(screen.getByRole("button", { name: "Crea il prodotto a mano" })).toBeDefined();
  });

  it("risultati misti: le opzioni, e sotto chi è di un altro ingrediente, per nome", async () => {
    stubSearch([FAGE, BURRO]);
    renderPanel();
    await screen.findByRole("option", { name: /Total 0%/ });
    expect(screen.queryByRole("option", { name: /Burro greco/ })).toBeNull();
    expect(
      screen.getByText("Un altro prodotto corrisponde, ma è di un altro ingrediente: burro.")
    ).toBeDefined();
  });

  it("una ricerca che non risponde lo dice, e lascia creare a mano", async () => {
    stubSearch("down");
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent(/non risponde/);
    expect(screen.getByRole("button", { name: "Crea il prodotto a mano" })).toBeDefined();
  });

  it("«Annulla» chiude il pannello", async () => {
    stubSearch([]);
    const { onCancel } = renderPanel();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalled();
  });
});
