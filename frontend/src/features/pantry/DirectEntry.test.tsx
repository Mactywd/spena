import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { createTestQueryClient } from "../../test/queryClient";
import { DirectEntry, type EntryDoor } from "./DirectEntry";
import type { Ingredient, PantryItem, Product } from "../../domain/types";

const YOGURT: Ingredient = {
  id: "i1", name: "yogurt greco", display_name: "Yogurt greco", category: "latticini", kind: "food",
};
const LENTICCHIE: Ingredient = {
  id: "i3", name: "lenticchie", display_name: "Lenticchie", category: "legumi", kind: "food",
};
const CECI_NERI: Ingredient = {
  id: "i9", name: "ceci neri", display_name: "ceci neri", category: "altro", kind: "food",
};
const FAGE: Product = {
  id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};
const FAGE_SENZA_CODICE: Product = { ...FAGE, barcode: null };
const PARMIGIANO: Product = {
  id: "p2", ingredient_id: "i8", ingredient_name: "burro", name: "Parmigiano Reggiano",
  brand: null, barcode: "8009876543217", source: "custom", nutrients: null, image_url: null,
};
const LENTICCHIE_COOP: Product = {
  id: "p7", ingredient_id: "i3", ingredient_name: "lenticchie", name: "Lenticchie rosse",
  brand: "Coop", barcode: "8001234567890", source: "openfoodfacts", nutrients: null, image_url: null,
};
const CODE = "8001234567890";
const CREATED: PantryItem = {
  id: "n1", ingredient_id: "i1", product_id: null, ingredient_name: "yogurt greco",
  ingredient_category: "latticini", ingredient_kind: "food", product_name: null, product_brand: null, status: "available",
  fill_percent: null, note: null, added_at: "2026-10-08T10:00:00Z", expires_on: null, expiry: null, ingredient_emoji: null,
};
const UNKNOWN = { found: false, origin: "unknown", product: null, suggestion: null, valid_checksum: true };
const inCatalog = (product: Product) => ({
  found: true, origin: "catalog", product, suggestion: null, valid_checksum: true,
});

/** Un fetch che risponde in base a percorso e metodo; la scrittura in dispensa risponde
 * sempre con la voce creata. */
function stubRoutedFetch(route: (path: string, init?: RequestInit) => [unknown, number?]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    if (path.endsWith("/pantry") && init?.method === "POST") {
      return Promise.resolve(new Response(JSON.stringify(CREATED), { status: 201 }));
    }
    const [body, status] = route(path, init);
    return Promise.resolve(new Response(JSON.stringify(body), { status: status ?? 200 }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function posts(spy: ReturnType<typeof stubRoutedFetch>, suffix: string) {
  return spy.mock.calls
    .filter(([url, init]) => String(url).endsWith(suffix) && (init as RequestInit)?.method === "POST")
    .map(([, init]) => JSON.parse(String((init as RequestInit).body)));
}

function renderEntry(door: EntryDoor, undoneItemIds: ReadonlySet<string> = new Set()) {
  const onEntered = vi.fn();
  const onClose = vi.fn();
  const client = createTestQueryClient();
  const tree = (undone: ReadonlySet<string>) => (
    <QueryClientProvider client={client}>
      <DirectEntry door={door} onEntered={onEntered} onClose={onClose} undoneItemIds={undone} />
    </QueryClientProvider>
  );
  const { rerender } = render(tree(undoneItemIds));
  return { onEntered, onClose, undo: (ids: string[]) => rerender(tree(new Set(ids))) };
}

async function readCode(code: string) {
  await userEvent.type(screen.getByLabelText("Codice a barre"), `${code}{Enter}`);
}

const LOOSE_BODY = (ingredientId: string) => ({
  ingredient_id: ingredientId, product_id: null, status: "available", expires_on: null, barcode: null,
});

describe("DirectEntry, dal +", () => {
  it("scelto l'ingrediente, la scheda dice «sfuso» e «Metti in dispensa» ha già il fuoco", async () => {
    const spy = stubRoutedFetch((path) => [path.includes("/ingredients/search") ? [YOGURT] : []]);
    const { onEntered, onClose } = renderEntry({ kind: "plus", text: "yog" });
    await userEvent.click(await screen.findByRole("option", { name: "Yogurt greco" }));
    const metti = screen.getByRole("button", { name: "Metti in dispensa" });
    expect(document.activeElement).toBe(metti);
    expect(screen.getByText("Sfuso, senza marca · yogurt greco")).toBeDefined();

    await userEvent.click(metti);
    await vi.waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(posts(spy, "/pantry")).toEqual([LOOSE_BODY("i1")]);
    expect(onEntered).toHaveBeenCalledWith(CREATED, "Yogurt greco");
  });

  it("un ingrediente che l'anagrafica non ha si crea lì: non si passa più dalla lista", async () => {
    const spy = stubRoutedFetch((path, init) =>
      path.endsWith("/ingredients") && init?.method === "POST" ? [CECI_NERI, 201] : [[]]
    );
    renderEntry({ kind: "plus", text: "ceci neri" });
    await userEvent.click(await screen.findByRole("button", { name: "Aggiungi «ceci neri»" }));
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    await userEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));

    await vi.waitFor(() => expect(posts(spy, "/pantry")).toEqual([LOOSE_BODY("i9")]));
    expect(posts(spy, "/ingredients")).toEqual([
      { name: "ceci neri", display_name: "ceci neri", category: "altro" },
    ]);
    expect(screen.queryByText(/scrivilo in/)).toBeNull();
  });

  it("la scadenza scritta nella scheda parte con la voce", async () => {
    const spy = stubRoutedFetch((path) => [path.includes("/ingredients/search") ? [YOGURT] : []]);
    renderEntry({ kind: "plus", text: "yog" });
    await userEvent.click(await screen.findByRole("option", { name: "Yogurt greco" }));
    await userEvent.click(screen.getByRole("button", { name: "+ scadenza per Yogurt greco" }));
    fireEvent.change(screen.getByLabelText("Scadenza di Yogurt greco"), {
      target: { value: "2026-10-20" },
    });
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa" }));
    await vi.waitFor(() => expect(posts(spy, "/pantry")[0]?.expires_on).toBe("2026-10-20"));
  });

  it("«Codice» aggancia un prodotto dell'ingrediente, e la scheda dice prodotto e marca", async () => {
    const spy = stubRoutedFetch((path) => {
      if (path.includes("/ingredients/search")) return [[YOGURT]];
      if (path.includes("/products/barcode/")) return [inCatalog(FAGE)];
      return [[]];
    });
    renderEntry({ kind: "plus", text: "yog" });
    await userEvent.click(await screen.findByRole("option", { name: "Yogurt greco" }));
    await userEvent.click(screen.getByRole("button", { name: "Codice a barre per Yogurt greco" }));
    expect(screen.getByRole("heading", { name: "Codice a barre per «Yogurt greco»" })).toBeDefined();
    await readCode("52010");

    expect(await screen.findByText("Fage · yogurt greco")).toBeDefined();
    expect(screen.getByText("Total 0%")).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa" }));
    await vi.waitFor(() =>
      expect(posts(spy, "/pantry")).toEqual([
        { ingredient_id: "i1", product_id: "p1", status: "available", expires_on: null, barcode: null },
      ])
    );
  });

  it("il codice di un prodotto di un altro ingrediente non si aggancia, e si dice quale", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/ingredients/search")) return [[YOGURT]];
      if (path.includes("/products/barcode/")) return [inCatalog(PARMIGIANO)];
      return [[]];
    });
    renderEntry({ kind: "plus", text: "yog" });
    await userEvent.click(await screen.findByRole("option", { name: "Yogurt greco" }));
    await userEvent.click(screen.getByRole("button", { name: "Codice a barre per Yogurt greco" }));
    await readCode("8009876543217");
    expect(await screen.findByText(/è di un altro ingrediente: burro/)).toBeDefined();
    expect(screen.queryByRole("button", { name: "Metti in dispensa" })).toBeNull();
  });

  it("il codice ignoto letto prima segue il prodotto scelto poi a catalogo (S8)", async () => {
    const spy = stubRoutedFetch((path) => {
      if (path.includes("/ingredients/search")) return [[YOGURT]];
      if (path.includes("/products/barcode/")) return [UNKNOWN];
      if (path.includes("/products/search")) return [[FAGE_SENZA_CODICE]];
      return [[]];
    });
    renderEntry({ kind: "plus", text: "yog" });
    await userEvent.click(await screen.findByRole("option", { name: "Yogurt greco" }));
    await userEvent.click(screen.getByRole("button", { name: "Codice a barre per Yogurt greco" }));
    await readCode(CODE);
    await screen.findByRole("heading", { name: /Nuovo prodotto per «Yogurt greco»/ });
    // il modulo si chiude: si torna alla scheda sfusa, e di lì al catalogo
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Cerca a catalogo per Yogurt greco" })
    );
    await userEvent.click(await screen.findByRole("option", { name: /Total 0%/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    await vi.waitFor(() =>
      expect(posts(spy, "/pantry")).toEqual([
        { ingredient_id: "i1", product_id: "p1", status: "available", expires_on: null, barcode: CODE },
      ])
    );
  });
});

describe("DirectEntry, «Scansiona»", () => {
  it("un prodotto a catalogo entra con due tocchi, e lo scanner torna per il prossimo", async () => {
    const spy = stubRoutedFetch(() => [inCatalog(FAGE)]);
    const { onEntered, onClose } = renderEntry({ kind: "scan" });
    expect(screen.getByRole("heading", { name: "Codice a barre" })).toBeDefined();
    await readCode("52010");
    const metti = await screen.findByRole("button", { name: "Metti in dispensa" });
    expect(document.activeElement).toBe(metti);
    await userEvent.click(metti);

    await vi.waitFor(() => expect(onEntered).toHaveBeenCalledWith(CREATED, "Fage Total 0%"));
    expect(posts(spy, "/pantry")).toEqual([
      { ingredient_id: "i1", product_id: "p1", status: "available", expires_on: null, barcode: null },
    ]);
    // in serie: lo scanner è di nuovo lì, col campo vuoto, e il pannello non si è chiuso
    expect(await screen.findByRole("heading", { name: "Codice a barre" })).toBeDefined();
    expect(screen.getByLabelText("Codice a barre")).toHaveValue("");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("in serie, lo stesso prodotto riletto lo dice, e non lo scrive da solo", async () => {
    const spy = stubRoutedFetch(() => [inCatalog(FAGE)]);
    renderEntry({ kind: "scan" });
    await readCode("52010");
    await userEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    await screen.findByRole("heading", { name: "Codice a barre" });
    await readCode("52010");
    expect(
      await screen.findByText("L'hai appena messo in dispensa: se è un'altra confezione, mettila pure.")
    ).toBeDefined();
    expect(posts(spy, "/pantry")).toHaveLength(1);
  });

  it("dopo un annullamento la nota sparisce", async () => {
    stubRoutedFetch(() => [inCatalog(FAGE)]);
    const { undo } = renderEntry({ kind: "scan" });
    await readCode("52010");
    await userEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    await screen.findByRole("heading", { name: "Codice a barre" });
    await readCode("52010");
    const nota = "L'hai appena messo in dispensa: se è un'altra confezione, mettila pure.";
    expect(await screen.findByText(nota)).toBeDefined();
    undo([CREATED.id]);
    expect(screen.queryByText(nota)).toBeNull();
  });

  it("un codice nuovo: l'ingrediente, poi il modulo già compilato senza la domanda, poi la scheda", async () => {
    const suggestion = { name: "Lenticchie rosse", brand: "Coop", barcode: CODE, nutrients: {}, image_url: null };
    const spy = stubRoutedFetch((path, init) => {
      if (path.includes("/products/barcode/")) {
        return [{ found: true, origin: "openfoodfacts", product: null, suggestion, valid_checksum: true }];
      }
      if (path.includes("/ingredients/search")) return [[LENTICCHIE]];
      if (path.endsWith("/products") && init?.method === "POST") return [LENTICCHIE_COOP, 201];
      return [[]];
    });
    renderEntry({ kind: "scan" });
    await readCode(CODE);

    expect(await screen.findByRole("heading", { name: "Di che ingrediente è?" })).toBeDefined();
    expect(screen.getByText("Su Open Food Facts è «Lenticchie rosse», di Coop.")).toBeDefined();
    await userEvent.type(screen.getByRole("textbox", { name: "Ingrediente" }), "lentic");
    await userEvent.click(await screen.findByRole("option", { name: "Lenticchie" }));

    expect(await screen.findByLabelText("Nome")).toHaveValue("Lenticchie rosse");
    expect(screen.queryByRole("heading", { name: /^È un/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Salva prodotto" }));

    expect(await screen.findByText("Coop · lenticchie")).toBeDefined();
    expect(posts(spy, "/products")[0]).toMatchObject({
      ingredient_id: "i3", name: "Lenticchie rosse", barcode: CODE,
    });
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa" }));
    await vi.waitFor(() =>
      expect(posts(spy, "/pantry")).toEqual([
        { ingredient_id: "i3", product_id: "p7", status: "available", expires_on: null, barcode: null },
      ])
    );
  });

  it("dal modulo si esce sfusi, con l'ingrediente scelto", async () => {
    const spy = stubRoutedFetch((path) => {
      if (path.includes("/products/barcode/")) return [UNKNOWN];
      if (path.includes("/ingredients/search")) return [[LENTICCHIE]];
      return [[]];
    });
    renderEntry({ kind: "scan" });
    await readCode(CODE);
    await userEvent.type(await screen.findByRole("textbox", { name: "Ingrediente" }), "lentic");
    await userEvent.click(await screen.findByRole("option", { name: "Lenticchie" }));
    await userEvent.click(await screen.findByRole("button", { name: "Sfuso, senza marca" }));
    expect(screen.getByText("Sfuso, senza marca · lenticchie")).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa" }));
    await vi.waitFor(() => expect(posts(spy, "/pantry")).toEqual([LOOSE_BODY("i3")]));
  });

  it("«Annulla» della scheda torna allo scanner; «Annulla» dello scanner chiude", async () => {
    stubRoutedFetch(() => [inCatalog(FAGE)]);
    const { onClose } = renderEntry({ kind: "scan" });
    await readCode("52010");
    // prima la scheda: finché non c'è, l'unico «Annulla» è quello dello scanner
    await screen.findByRole("button", { name: "Metti in dispensa" });
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("heading", { name: "Codice a barre" })).toBeDefined();
    expect(onClose).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onClose).toHaveBeenCalled();
  });
});
