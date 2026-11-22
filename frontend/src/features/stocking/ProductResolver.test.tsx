import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { createTestQueryClient } from "../../test/queryClient";
import { ProductResolver, type ResolverIngredient } from "./ProductResolver";
import type { Resolution } from "./stockingView";
import type { Ingredient, Product } from "../../domain/types";

const YOGURT: ResolverIngredient = { id: "i1", name: "yogurt greco", kind: "food" };
const LENTICCHIE: Ingredient = {
  id: "i3", name: "lenticchie", display_name: "Lenticchie", category: "legumi", kind: "food",
};
const FAGE: Product = {
  id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};
// un parmigiano registrato sotto «burro» (S9): con l'ingrediente atteso non si aggancia,
// senza porta il suo
const PARMIGIANO: Product = {
  id: "p2", ingredient_id: "i8", ingredient_name: "burro", name: "Parmigiano Reggiano",
  brand: null, barcode: "8009876543217", source: "custom", nutrients: null, image_url: null,
};
const DECORTICATE: Product = {
  id: "p5", ingredient_id: "i3", ingredient_name: "lenticchie", name: "Lenticchie decorticate",
  brand: "Coop", barcode: null, source: "custom", nutrients: null, image_url: null,
};
const CODE = "8001234567890";
const UNKNOWN = { found: false, origin: "unknown", product: null, suggestion: null, valid_checksum: true };
const IN_CATALOG = (product: Product) => ({
  found: true, origin: "catalog", product, suggestion: null, valid_checksum: true,
});

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function stubRoutedFetch(route: (path: string, init?: RequestInit) => unknown) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => Promise.resolve(respond(route(String(url), init))));
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** Il resolver come lo usa uno schermo: il codice ricordato sta fuori, e sopravvive. */
function Harness(props: {
  ingredient: ResolverIngredient | null;
  label: string | null;
  onResolved: (resolution: Resolution, ingredient: ResolverIngredient) => void;
  onCancel: (trigger: string) => void;
}) {
  const [code, setCode] = useState<string | undefined>(undefined);
  return (
    <ProductResolver
      {...props}
      start="scanner"
      rememberedCode={code}
      onRememberCode={(next) => setCode(next ?? undefined)}
    />
  );
}

function renderResolver(over: { ingredient?: ResolverIngredient | null; label?: string | null } = {}) {
  const onResolved = vi.fn();
  const onCancel = vi.fn();
  const client = createTestQueryClient();
  render(
    <QueryClientProvider client={client}>
      <Harness
        ingredient={over.ingredient === undefined ? YOGURT : over.ingredient}
        label={over.label === undefined ? "yogurt greco" : over.label}
        onResolved={onResolved}
        onCancel={onCancel}
      />
    </QueryClientProvider>
  );
  return { onResolved, onCancel };
}

async function readCode(code: string) {
  await userEvent.type(screen.getByLabelText("Codice a barre"), `${code}{Enter}`);
}

describe("ProductResolver", () => {
  it("con l'ingrediente, il codice di un suo prodotto risolve col prodotto e con l'ingrediente atteso", async () => {
    stubRoutedFetch(() => IN_CATALOG(FAGE));
    const { onResolved } = renderResolver();
    await readCode("52010");
    await vi.waitFor(() =>
      expect(onResolved).toHaveBeenCalledWith({ kind: "product", product: FAGE }, YOGURT)
    );
  });

  it("un esito arrivato dopo «Annulla» non risolve niente", async () => {
    // react-query chiama gli `on…` di una mutazione anche quando nessuno guarda più
    let answer: (response: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => { answer = resolve; }))
    );
    const { onResolved, onCancel } = renderResolver();
    await readCode("52010");
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalledWith("scanner");

    await act(async () => {
      answer(respond(IN_CATALOG(FAGE)));
      await new Promise((resolve) => setTimeout(resolve, 50));
    });
    expect(onResolved).not.toHaveBeenCalled();
  });

  it("senza ingrediente, il prodotto di qualunque ingrediente risolve, col suo ingrediente", async () => {
    stubRoutedFetch(() => IN_CATALOG(PARMIGIANO));
    const { onResolved } = renderResolver({ ingredient: null, label: null });
    expect(screen.getByRole("heading", { name: "Codice a barre" })).toBeDefined();
    await readCode("8009876543217");
    await vi.waitFor(() =>
      expect(onResolved).toHaveBeenCalledWith(
        { kind: "product", product: PARMIGIANO },
        { id: "i8", name: "burro", kind: null }
      )
    );
  });

  it("senza ingrediente, un codice nuovo chiede l'ingrediente; dal modulo il catalogo porta il codice letto (S8)", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/products/barcode/")) return UNKNOWN;
      if (path.includes("/ingredients/search")) return [LENTICCHIE];
      if (path.includes("/products/search")) return [DECORTICATE];
      return [];
    });
    const { onResolved, onCancel } = renderResolver({ ingredient: null, label: null });
    await readCode(CODE);

    expect(await screen.findByRole("heading", { name: "Di che ingrediente è?" })).toBeDefined();
    expect(screen.getByText(`Il codice ${CODE} non è in catalogo né su Open Food Facts.`)).toBeDefined();
    await userEvent.type(screen.getByRole("textbox", { name: "Ingrediente" }), "lentic");
    await userEvent.click(await screen.findByRole("option", { name: "Lenticchie" }));

    // il modulo, senza la domanda «È un …?»: l'ingrediente l'ha appena detto chi legge
    expect(await screen.findByRole("heading", { name: /Nuovo prodotto per «Lenticchie»/ })).toBeDefined();
    expect(screen.queryByRole("heading", { name: /^È un/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Cerca a catalogo" }));
    await userEvent.click(await screen.findByRole("option", { name: /Lenticchie decorticate/ }));

    expect(onResolved).toHaveBeenCalledWith(
      { kind: "product", product: DECORTICATE, barcode: CODE },
      { id: "i3", name: "lenticchie", kind: "food" }
    );
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("senza ingrediente, dal modulo si esce sfusi; e «Annulla» dopo il codice torna allo scanner", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/products/barcode/")) return UNKNOWN;
      if (path.includes("/ingredients/search")) return [LENTICCHIE];
      return [];
    });
    const { onResolved, onCancel } = renderResolver({ ingredient: null, label: null });
    await readCode(CODE);
    await screen.findByRole("heading", { name: "Di che ingrediente è?" });
    // c'è una confezione in mano: «Annulla» non chiude, torna a leggere
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("heading", { name: "Codice a barre" })).toBeDefined();
    expect(screen.getByLabelText("Codice a barre")).toHaveValue("");
    expect(onCancel).not.toHaveBeenCalled();

    await readCode(CODE);
    await userEvent.type(await screen.findByRole("textbox", { name: "Ingrediente" }), "lentic");
    await userEvent.click(await screen.findByRole("option", { name: "Lenticchie" }));
    await userEvent.click(await screen.findByRole("button", { name: "Sfuso, senza marca" }));
    expect(onResolved).toHaveBeenCalledWith(
      { kind: "loose" },
      { id: "i3", name: "lenticchie", kind: "food" }
    );
  });

  it("con l'ingrediente, il modulo non offre lo sfuso né il catalogo: la voce ha già le sue strade", async () => {
    stubRoutedFetch(() => UNKNOWN);
    renderResolver();
    await readCode(CODE);
    expect(await screen.findByRole("heading", { name: /Nuovo prodotto per «yogurt greco»/ })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Sfuso, senza marca" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Cerca a catalogo" })).toBeNull();
  });
});
