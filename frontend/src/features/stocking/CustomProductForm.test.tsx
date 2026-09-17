import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CustomProductForm } from "./CustomProductForm";
import type { ProductSuggestion } from "./CustomProductForm";

const CREATED = {
  id: "p9", ingredient_id: "i1", name: "Passata Rustica", brand: "Mutti",
  barcode: "88990", source: "openfoodfacts", nutrients: null, image_url: null,
};

// quel che Open Food Facts restituisce davvero: il backend mappa otto nutrienti
// (backend/app/services/openfoodfacts.py), non i quattro che il modulo mostra
const SUGGESTION: ProductSuggestion = {
  name: "Passata Rustica",
  brand: "Mutti",
  barcode: "88990",
  nutrients: {
    kcal: 30, protein: 1.4, carbs: 5.6, sugars: 4.9,
    fat: 0.3, saturated_fat: 0.1, fiber: 1.2, salt: 0.06,
  },
  image_url: "https://images.off/88990.jpg",
};

function stubFetch() {
  const spy = vi.fn(() => Promise.resolve(new Response(JSON.stringify(CREATED), { status: 201 })));
  vi.stubGlobal("fetch", spy);
  return spy;
}

function bodyOf(spy: ReturnType<typeof stubFetch>) {
  // il mock non dichiara parametri, ma fetch li riceve: le chiamate si rileggono
  // con la forma vera
  const calls = spy.mock.calls as unknown as [string, RequestInit | undefined][];
  const call = calls.find(([url]) => url.endsWith("/products"));
  return JSON.parse(String(call?.[1]?.body));
}

function renderForm(props: Partial<Parameters<typeof CustomProductForm>[0]> = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <CustomProductForm
        ingredientId="i1"
        itemLabel="passata"
        onCreated={vi.fn()}
        onCancel={vi.fn()}
        {...props}
      />
    </QueryClientProvider>
  );
}

describe("CustomProductForm", () => {
  it("un nutriente lasciato vuoto resta assente, non diventa zero", async () => {
    // zero è un'affermazione, l'assenza è la verità: un campo vuoto non deve
    // mai comparire nel corpo della richiesta
    const spy = stubFetch();
    renderForm();

    await userEvent.type(screen.getByLabelText("Nome"), "Passata Rustica");
    await userEvent.type(screen.getByLabelText("Calorie per 100 g"), "30");
    await userEvent.click(screen.getByRole("button", { name: "Salva prodotto" }));

    await vi.waitFor(() => expect(spy).toHaveBeenCalled());
    const body = bodyOf(spy);
    expect(body.nutrients).toEqual({ kcal: 30 });
    expect(body.nutrients).not.toHaveProperty("protein");
    expect(body.nutrients).not.toHaveProperty("carbs");
    expect(body.nutrients).not.toHaveProperty("fat");
  });

  it("senza nessun nutriente compilato non manda affatto la chiave nutrients", async () => {
    const spy = stubFetch();
    renderForm();

    await userEvent.type(screen.getByLabelText("Nome"), "Pane del forno sotto casa");
    await userEvent.click(screen.getByRole("button", { name: "Salva prodotto" }));

    await vi.waitFor(() => expect(spy).toHaveBeenCalled());
    const body = bodyOf(spy);
    expect(body).not.toHaveProperty("nutrients");
  });

  it("confermando un suggerimento non si perde nessun nutriente, né la provenienza", async () => {
    // la conferma è l'unico momento in cui quei dati esistono: quel che non si
    // riporta qui è perso per sempre (docstring di ProductCreate)
    const spy = stubFetch();
    renderForm({ suggestion: SUGGESTION, barcode: "88990" });

    await userEvent.click(screen.getByRole("button", { name: "Salva prodotto" }));

    await vi.waitFor(() => expect(spy).toHaveBeenCalled());
    const body = bodyOf(spy);
    expect(body.nutrients).toEqual(SUGGESTION.nutrients);
    expect(body.source).toBe("openfoodfacts");
    expect(body.image_url).toBe(SUGGESTION.image_url);
    expect(body.barcode).toBe("88990");
  });

  it("correggere un valore del suggerimento non cancella gli altri", async () => {
    const spy = stubFetch();
    renderForm({ suggestion: SUGGESTION, barcode: "88990" });

    await userEvent.clear(screen.getByLabelText("Calorie per 100 g"));
    await userEvent.type(screen.getByLabelText("Calorie per 100 g"), "32");
    await userEvent.click(screen.getByRole("button", { name: "Salva prodotto" }));

    await vi.waitFor(() => expect(spy).toHaveBeenCalled());
    const body = bodyOf(spy);
    expect(body.nutrients).toEqual({ ...SUGGESTION.nutrients, kcal: 32 });
  });

  it("si può uscire dal modulo senza salvare niente", async () => {
    // un 409 su un codice già in catalogo non deve lasciare il riquadro
    // incollato allo schermo per sempre
    stubFetch();
    const onCancel = vi.fn();
    renderForm({ onCancel });

    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));

    expect(onCancel).toHaveBeenCalled();
  });

  it("dice a quale voce appartiene il prodotto che si sta creando", () => {
    stubFetch();
    renderForm({ itemLabel: "mele" });

    expect(screen.getByRole("heading", { name: /Nuovo prodotto per «mele»/ })).toBeDefined();
  });

  it("per un non alimentare non chiede i nutrienti, e non ne manda", async () => {
    // quattro campi senza senso su un detersivo, e un `nutrients: {}` che
    // sarebbe un'affermazione su valori che non esistono
    const spy = stubFetch();
    renderForm({ itemLabel: "detersivo", isNonFood: true });

    expect(screen.queryByLabelText("Calorie per 100 g")).toBeNull();
    await userEvent.type(screen.getByLabelText("Nome"), "Dash");
    await userEvent.click(screen.getByRole("button", { name: "Salva prodotto" }));

    await vi.waitFor(() => expect(spy).toHaveBeenCalled());
    const body = bodyOf(spy);
    expect(body).not.toHaveProperty("nutrients");
  });
});
