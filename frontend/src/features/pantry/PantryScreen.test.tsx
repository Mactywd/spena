import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PantryScreen } from "./PantryScreen";

const ITEMS = [
  { id: "p1", ingredient_id: "i1", product_id: "pr1", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Total 0%", product_brand: "Fage",
    status: "available", note: null, added_at: "2026-09-11T10:00:00Z" },
  { id: "p2", ingredient_id: "i1", product_id: "pr2", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", product_name: "Pesca", product_brand: "Carrefour",
    status: "low", note: null, added_at: "2026-09-11T10:00:00Z" },
  { id: "p3", ingredient_id: "i2", product_id: null, ingredient_name: "mela",
    ingredient_category: "frutta", product_name: null, product_brand: null,
    status: "available", note: null, added_at: "2026-09-11T10:00:00Z" },
];

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PantryScreen />
    </QueryClientProvider>
  );
}

describe("PantryScreen", () => {
  it("mostra marca e nome del prodotto quando li conosce", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(ITEMS), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("Total 0%")).toBeDefined();
    expect(screen.getByText("Fage")).toBeDefined();
  });

  it("per gli sfusi mostra il nome dell'ingrediente", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(ITEMS), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("mela")).toBeDefined();
  });

  it("elenca separatamente due prodotti dello stesso ingrediente", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(ITEMS), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("Total 0%")).toBeDefined();
    expect(screen.getByText("Pesca")).toBeDefined();
  });

  it("cambiare stato manda una PATCH con il nuovo valore e lo schermo lo rispecchia", async () => {
    // la PATCH risponde con la riga, la GET successiva con la lista aggiornata:
    // distinguerle è ciò che rende il test una copertura del ri-render e non solo
    // della chiamata
    const changed = [{ ...ITEMS[0], status: "low" }, ITEMS[1], ITEMS[2]];
    const spy = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return Promise.resolve(
          new Response(JSON.stringify({ ...ITEMS[0], status: "low" }), { status: 200 })
        );
      }
      const body = spy.mock.calls.some(([, i]) => i?.method === "PATCH") ? changed : ITEMS;
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);

    renderScreen();
    const row = (await screen.findByText("Total 0%")).closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Quasi finito" }));

    const patch = spy.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(patch?.[0]).toContain("/pantry/p1");
    expect(JSON.parse(patch?.[1].body)).toEqual({ status: "low" });

    await waitFor(() => {
      const updated = screen.getByText("Total 0%").closest("li")!;
      expect(within(updated).getByRole("button", { name: "Quasi finito" }))
        .toHaveAttribute("aria-pressed", "true");
    });
  });

  it("una modifica rifiutata lo dice, accanto alla voce giusta", async () => {
    const spy = vi.fn().mockImplementation((_url: string, init?: RequestInit) =>
      init?.method === "PATCH"
        ? Promise.resolve(new Response(JSON.stringify({ detail: "no" }), { status: 500 }))
        : Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    const row = (await screen.findByText("Total 0%")).closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Quasi finito" }));

    expect(await within(row).findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
    const other = screen.getByText("Pesca").closest("li")!;
    expect(within(other).queryByRole("alert")).toBeNull();
  });

  it("si può togliere una voce dalla dispensa", async () => {
    const spy = vi.fn().mockImplementation((_url: string, init?: RequestInit) =>
      init?.method === "PATCH"
        ? Promise.resolve(new Response(JSON.stringify(ITEMS[0]), { status: 200 }))
        : Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    const row = (await screen.findByText("Total 0%")).closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Togli dalla dispensa" }));

    const patch = spy.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(patch?.[0]).toContain("/pantry/p1");
    expect(JSON.parse(patch?.[1].body)).toEqual({ archived: true });
  });

  it("mentre una modifica è in volo i controlli di quella voce sono bloccati", async () => {
    // due PATCH sulla stessa voce arrivano in ordine ignoto e l'ultima a rispondere
    // vince: la seconda non deve nemmeno poter partire
    const spy = vi.fn().mockImplementation((_url: string, init?: RequestInit) =>
      init?.method === "PATCH"
        ? new Promise<Response>(() => {})
        : Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    const row = (await screen.findByText("Total 0%")).closest("li")!;
    await userEvent.click(within(row).getByRole("button", { name: "Quasi finito" }));

    await waitFor(() =>
      expect(within(row).getByRole("button", { name: "Finito" })).toBeDisabled()
    );
    expect(within(row).getByRole("button", { name: "Togli dalla dispensa" })).toBeDisabled();
    const other = screen.getByText("Pesca").closest("li")!;
    expect(within(other).getByRole("button", { name: "Finito" })).not.toBeDisabled();
  });

  it("dice cosa fare quando la dispensa è vuota", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderScreen();
    expect(await screen.findByText(/Dispensa vuota/)).toBeDefined();
  });

  it("un caricamento fallito non si traveste da dispensa vuota", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "errore" }), { status: 500 })
    ));
    renderScreen();
    expect(await screen.findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
    expect(screen.queryByText(/Dispensa vuota/)).toBeNull();
  });
});
