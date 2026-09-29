import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ScannerPanel } from "./ScannerPanel";
import type { BarcodeLookup, Product, ShoppingItem } from "../../domain/types";

const YOGURT: ShoppingItem = {
  id: "s1", raw_text: "yogurt greco", ingredient_id: "i1", ingredient_name: "yogurt greco",
  ingredient_category: "latticini", ingredient_kind: "food", status: "checked", reason: "manual",
  created_at: "2026-09-29T10:00:00Z",
};
const FAGE: Product = {
  id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};
// il caso di S9 visto dall'altra parte: un parmigiano registrato sotto «burro»
const PARMIGIANO: Product = {
  id: "p2", ingredient_id: "i8", ingredient_name: "burro", name: "Parmigiano Reggiano",
  brand: null, barcode: "8009876543217", source: "custom", nutrients: null, image_url: null,
};

function lookup(over: Partial<BarcodeLookup>): BarcodeLookup {
  return { found: false, origin: "unknown", product: null, suggestion: null, valid_checksum: true, ...over };
}

/** Il lookup risponde sempre lo stesso esito, o non risponde. */
function stubLookup(answer: BarcodeLookup | "down") {
  const spy = vi.fn((_url: unknown) =>
    Promise.resolve(
      answer === "down"
        ? new Response(JSON.stringify({ detail: "giù" }), { status: 500 })
        : new Response(JSON.stringify(answer), { status: 200 })
    )
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderPanel() {
  const props = {
    onProduct: vi.fn(), onNewCode: vi.fn(), onUnlinkedCode: vi.fn(), onCreateByHand: vi.fn(),
    onCancel: vi.fn(),
  };
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ScannerPanel item={YOGURT} ingredientId="i1" {...props} />
    </QueryClientProvider>
  );
  return props;
}

describe("ScannerPanel", () => {
  it("il titolo dice per quale voce è aperto (S10)", () => {
    stubLookup(lookup({}));
    renderPanel();
    expect(screen.getByRole("heading", { name: "Codice a barre per «yogurt greco»" })).toBeDefined();
  });

  it("il campo del codice chiede la tastiera dei numeri (S10)", () => {
    stubLookup(lookup({}));
    renderPanel();
    expect(screen.getByLabelText("Codice a barre")).toHaveAttribute("inputmode", "numeric");
  });

  it("«Cerca» cerca il codice scritto, senza bisogno dell'Invio (S10)", async () => {
    const spy = stubLookup(lookup({ found: true, origin: "catalog", product: FAGE }));
    const { onProduct } = renderPanel();
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010");
    await userEvent.click(screen.getByRole("button", { name: "Cerca" }));
    await waitFor(() => expect(onProduct).toHaveBeenCalledWith(FAGE));
    expect(String(spy.mock.calls[0][0])).toContain("/products/barcode/52010");
  });

  it("l'Invio cerca anche lui, e non arriva a nessun altro pulsante", async () => {
    stubLookup(lookup({ found: true, origin: "catalog", product: FAGE }));
    const { onProduct } = renderPanel();
    const field = screen.getByLabelText("Codice a barre");
    await userEvent.type(field, "52010");
    // `false`: l'evento è stato annullato (`preventDefault`)
    expect(fireEvent.keyDown(field, { key: "Enter" })).toBe(false);
    await waitFor(() => expect(onProduct).toHaveBeenCalledWith(FAGE));
  });

  it("un campo vuoto non cerca niente", async () => {
    const spy = stubLookup(lookup({}));
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: "Cerca" }));
    expect(spy).not.toHaveBeenCalled();
  });

  it("mentre cerca, «Cerca» si spegne ma tiene il fuoco, e non parte una seconda ricerca", async () => {
    let release: (response: Response) => void = () => {};
    const spy = vi.fn(() => new Promise<Response>((resolve) => { release = resolve; }));
    vi.stubGlobal("fetch", spy);
    renderPanel();
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010");
    const cerca = screen.getByRole("button", { name: "Cerca" });
    await userEvent.click(cerca);
    await waitFor(() => expect(cerca).toHaveAttribute("aria-disabled", "true"));
    // `aria-disabled` e non `disabled`: un pulsante che diventa `disabled` perde il fuoco
    expect(cerca).not.toBeDisabled();
    await userEvent.click(cerca);
    expect(spy).toHaveBeenCalledTimes(1);
    release(new Response(JSON.stringify(lookup({})), { status: 200 }));
  });

  it("senza fotocamera offre di creare il prodotto a mano, e ci porta (S10)", async () => {
    stubLookup(lookup({}));
    const { onCreateByHand } = renderPanel();
    // jsdom non ha fotocamera: è il caso del telefono che la nega
    await userEvent.click(await screen.findByRole("button", { name: "Crea il prodotto a mano" }));
    expect(onCreateByHand).toHaveBeenCalledWith("", undefined);
  });

  it("il prodotto di un altro ingrediente non si aggancia, e si dice quale, in uno stato sempre presente (F9)", async () => {
    stubLookup(lookup({ found: true, origin: "catalog", product: PARMIGIANO }));
    const { onProduct, onUnlinkedCode } = renderPanel();
    // la cornice `role="status"` è già nel DOM, vuota: uno screen reader annuncia il
    // cambiamento di un nodo già presente, non uno che arriva insieme al testo (F9)
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("");
    await userEvent.type(screen.getByLabelText("Codice a barre"), "8009876543217{Enter}");
    await waitFor(() =>
      expect(status).toHaveTextContent("«Parmigiano Reggiano» è di un altro ingrediente: burro.")
    );
    expect(status).not.toHaveAttribute("role", "alert");
    expect(status.className).not.toContain("text-danger");
    expect(onProduct).not.toHaveBeenCalled();
    // il codice è già di un altro prodotto: non segue la voce (S8)
    expect(onUnlinkedCode).toHaveBeenCalledWith(null);
  });

  it("un codice nuovo va avanti con quel che Open Food Facts ne sa", async () => {
    const suggestion = {
      name: "Spaghetti n.5", brand: "Barilla", barcode: "8076800195057", nutrients: {},
      image_url: null,
    };
    stubLookup(lookup({ found: true, origin: "openfoodfacts", suggestion }));
    const { onNewCode } = renderPanel();
    await userEvent.type(screen.getByLabelText("Codice a barre"), "8076800195057{Enter}");
    await waitFor(() => expect(onNewCode).toHaveBeenCalledWith("8076800195057", suggestion));
  });

  it("un codice che non torna si ferma qui, correggibile, e si può usare lo stesso (S20)", async () => {
    stubLookup(lookup({ valid_checksum: false }));
    const { onNewCode } = renderPanel();
    const field = screen.getByLabelText("Codice a barre");
    await userEvent.type(field, "1234{Enter}");
    expect(await screen.findByText("Questo codice non torna: ricontrollalo.")).toBeDefined();
    expect(field).toHaveValue("1234");
    expect(onNewCode).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Usa questo codice lo stesso" }));
    expect(onNewCode).toHaveBeenCalledWith("1234", null);
  });

  it("un lookup fallito lo dice, tiene il codice, e offre la creazione a mano una volta sola", async () => {
    stubLookup("down");
    const { onCreateByHand, onUnlinkedCode } = renderPanel();
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010{Enter}");
    expect(await screen.findByText(/non sono riuscito a leggere il codice/i)).toBeDefined();
    expect(screen.getByLabelText("Codice a barre")).toHaveValue("52010");
    expect(onUnlinkedCode).toHaveBeenCalledWith("52010");
    // senza fotocamera il pulsante c'era già: resta uno, e ora porta il codice
    const create = screen.getAllByRole("button", { name: "Crea il prodotto a mano" });
    expect(create).toHaveLength(1);
    await userEvent.click(create[0]);
    expect(onCreateByHand).toHaveBeenCalledWith("52010", "failed");
  });

  it("«Annulla» chiude il pannello, ed è in fondo", async () => {
    stubLookup(lookup({}));
    const { onCancel } = renderPanel();
    const annulla = screen.getByRole("button", { name: "Annulla" });
    const field = screen.getByLabelText("Codice a barre");
    expect(field.compareDocumentPosition(annulla) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await userEvent.click(annulla);
    expect(onCancel).toHaveBeenCalled();
  });
});
