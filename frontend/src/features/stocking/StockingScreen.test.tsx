import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { StockingScreen } from "./StockingScreen";

const CHECKED = [
  { id: "s1", raw_text: "yogurt greco", ingredient_id: "i1", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", status: "checked", reason: "manual",
    created_at: "2026-09-11T10:00:00Z" },
  { id: "s2", raw_text: "mele", ingredient_id: "i2", ingredient_name: "mela",
    ingredient_category: "frutta", status: "checked", reason: "manual",
    created_at: "2026-09-11T10:05:00Z" },
];

// "un ingrediente che risolve a niente": una voce spuntata senza ingredient_id,
// perché il testo libero non ha mai trovato un corrispondente. Non deve sparire
// in silenzio: deve restare sistemabile a mano, abbinando un ingrediente.
const UNMATCHED = [
  { id: "s3", raw_text: "cosa strana", ingredient_id: null, ingredient_name: null,
    ingredient_category: null, status: "checked", reason: "manual",
    created_at: "2026-09-11T10:10:00Z" },
];

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <StockingScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

describe("StockingScreen", () => {
  it("elenca solo le voci spuntate", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(CHECKED)));
    renderScreen();
    expect(await screen.findByText("yogurt greco")).toBeDefined();
    expect(screen.getByText("mele")).toBeDefined();
  });

  it("permette di confermare una voce come sfusa, senza prodotto", async () => {
    const spy = vi.fn()
      .mockResolvedValueOnce(respond(CHECKED))
      .mockResolvedValue(respond({ created: 1 }, 201));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
    await userEvent.click(screen.getByRole("button", { name: /Metti in dispensa/ }));

    const post = spy.mock.calls.find(([url]) => String(url).endsWith("/shopping-list/stock"));
    expect(JSON.parse(post?.[1].body).entries).toEqual([
      { shopping_item_id: "s2", ingredient_id: "i2", product_id: null },
    ]);
  });

  it("un codice a barre noto aggancia subito il prodotto di catalogo", async () => {
    const lookup = {
      found: true, origin: "catalog", suggestion: null,
      product: { id: "p1", ingredient_id: "i1", name: "Total 0%", brand: "Fage",
                 barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null },
    };
    const spy = vi.fn()
      .mockResolvedValueOnce(respond(CHECKED))
      .mockResolvedValue(respond(lookup));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    // lo scanner in ambiente di test non legge: il campo manuale copre il caso
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010{Enter}");

    expect(await screen.findByText("Total 0%")).toBeDefined();
  });

  it("un codice ignoto apre la creazione manuale invece di un errore", async () => {
    const spy = vi.fn()
      .mockResolvedValueOnce(respond(CHECKED))
      .mockResolvedValue(respond({ found: false, origin: "unknown", product: null,
                                   suggestion: null }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    await userEvent.type(screen.getByLabelText("Codice a barre"), "000{Enter}");

    expect(await screen.findByRole("heading", { name: /Nuovo prodotto/ })).toBeDefined();
  });

  it("un suggerimento di Open Food Facts precompila il modulo, non lo lascia vuoto", async () => {
    // la fiche esiste, solo non è ancora in catalogo: buttarla via e far
    // ridigitare tutto da zero sarebbe un mezzo vicolo cieco
    const lookup = {
      found: true, origin: "openfoodfacts", product: null,
      suggestion: { name: "Passata Rustica", brand: "Mutti", barcode: "88990",
                    nutrients: { kcal: 30 }, image_url: null },
    };
    const spy = vi.fn()
      .mockResolvedValueOnce(respond(CHECKED))
      .mockResolvedValue(respond(lookup));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Codice.*yogurt greco/i }));
    await userEvent.type(screen.getByLabelText("Codice a barre"), "88990{Enter}");

    await screen.findByRole("heading", { name: /Nuovo prodotto/ });
    expect(screen.getByLabelText("Nome")).toHaveValue("Passata Rustica");
    expect(screen.getByLabelText("Marca")).toHaveValue("Mutti");
    expect(screen.getByLabelText("Calorie per 100 g")).toHaveValue(30);
  });

  it("non manda in dispensa nulla se non hai confermato niente", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(CHECKED)));
    renderScreen();
    await screen.findByText("mele");
    expect(screen.getByRole("button", { name: /Metti in dispensa/ })).toBeDisabled();
  });

  it("una voce senza ingrediente abbinato si sistema abbinandone uno a mano", async () => {
    const matches = [{ id: "i9", name: "cosa strana", display_name: "Cosa Strana",
                        category: "varie" }];
    const spy = vi.fn()
      .mockResolvedValueOnce(respond(UNMATCHED))
      .mockResolvedValue(respond(matches));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await screen.findByText("cosa strana");

    // niente pulsanti di sistemazione finché la voce non ha un ingrediente:
    // comparirebbero comandi che alla conferma sparirebbero in silenzio
    expect(screen.queryByRole("button", { name: /Sfuso/i })).toBeNull();

    const matchField = screen.getByLabelText(/Abbina un ingrediente/i);
    await userEvent.type(matchField, "strana");

    await userEvent.click(await screen.findByRole("option", { name: /Cosa Strana/i }));
    expect(await screen.findByRole("button", { name: /Sfuso.*cosa strana/i })).toBeDefined();
  });
});
