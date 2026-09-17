import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ShoppingListScreen } from "./ShoppingListScreen";

const ITEMS = [
  { id: "s1", raw_text: "pomodoro", ingredient_id: "i1", ingredient_name: "pomodoro",
    ingredient_category: "verdura", status: "pending", reason: "manual",
    created_at: "2026-09-11T10:00:00Z" },
  { id: "s2", raw_text: "Total 0%", ingredient_id: "i2", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", status: "pending", reason: "finished_while_cooking",
    created_at: "2026-09-11T11:00:00Z" },
  { id: "s3", raw_text: "cosa verde", ingredient_id: null, ingredient_name: null,
    ingredient_category: null, status: "checked", reason: "manual",
    created_at: "2026-09-11T12:00:00Z" },
];

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ShoppingListScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ShoppingListScreen", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(ITEMS), { status: 200 })
    ));
  });

  it("raggruppa le voci per reparto, per seguire il giro del supermercato", async () => {
    renderScreen();
    expect(await screen.findByRole("heading", { name: "verdura" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "latticini" })).toBeDefined();
  });

  it("segnala le voci rientrate dopo aver cucinato", async () => {
    renderScreen();
    expect(await screen.findByText("rientrata perché finita cucinando")).toBeDefined();
  });

  it("mostra le voci non risolte col testo che hai scritto", async () => {
    renderScreen();
    expect(await screen.findByText("cosa verde")).toBeDefined();
  });

  it("spuntando una voce la manda in stato checked", async () => {
    const spy = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(ITEMS), { status: 200 }))
      .mockResolvedValue(new Response(JSON.stringify({ ...ITEMS[0], status: "checked" }),
        { status: 200 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.click(await screen.findByRole("checkbox", { name: /pomodoro/ }));

    const patch = spy.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(patch?.[0]).toContain("/shopping-list/s1");
    expect(JSON.parse(patch?.[1].body)).toEqual({ status: "checked" });
  });

  it("offre di sistemare la spesa quando c'è almeno una voce spuntata", async () => {
    renderScreen();
    // la scheda è sempre presente: si aspetta che il conteggio arrivi, non il link
    await screen.findByText("1 voce spuntata da mettere via");
    expect(screen.getByRole("link", { name: /Sistema la spesa/ })).toHaveClass("bg-low-tint");
  });

  it("l'ingresso a «Sistema la spesa» resta anche senza voci spuntate", async () => {
    // stub: la lista risponde con voci tutte `pending`
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(ITEMS.map((i) => ({ ...i, status: "pending" }))), { status: 200 })
    ));
    renderScreen();
    // si aspetta che la lista sia arrivata, non solo lo stato iniziale a zero
    await screen.findByText("cosa verde");
    const link = screen.getByRole("link", { name: /Sistema la spesa/ });
    expect(link.getAttribute("href")).toBe("/sistema");
    expect(screen.getByText("Niente di spuntato, per ora")).toBeDefined();
  });

  // M1: senza questo comando una voce scritta per sbaglio resta in lista per la vita
  // dell'app, e l'unico modo di farla sparire — spuntarla e sistemarla in dispensa —
  // crea una voce di dispensa falsa.
  it("si può togliere dalla lista una voce scritta per sbaglio", async () => {
    const spy = vi.fn()
      .mockResolvedValue(new Response(JSON.stringify(ITEMS), { status: 200 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.click(
      await screen.findByRole("button", { name: "Togli pomodoro dalla lista" })
    );

    const patch = spy.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(patch?.[0]).toContain("/shopping-list/s1");
    expect(JSON.parse(patch?.[1].body)).toEqual({ status: "archived" });
  });

  it("una modifica rifiutata lo dice, accanto alla voce giusta", async () => {
    const spy = vi.fn().mockImplementation((_url: string, init?: RequestInit) =>
      init?.method === "PATCH"
        ? Promise.resolve(new Response(JSON.stringify({ detail: "no" }), { status: 500 }))
        : Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    const row = (await screen.findByText("pomodoro")).closest("li")!;
    await userEvent.click(
      within(row).getByRole("button", { name: "Togli pomodoro dalla lista" })
    );

    expect(await within(row).findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
    const other = screen.getByText("Total 0%").closest("li")!;
    expect(within(other).queryByRole("alert")).toBeNull();
  });

  it("mentre una scrittura è in volo i controlli di quella voce sono bloccati", async () => {
    // due PATCH sulla stessa riga arrivano in ordine ignoto e l'ultima a rispondere
    // vince: togliere una voce mentre la spunta è in volo non deve nemmeno partire
    const spy = vi.fn().mockImplementation((_url: string, init?: RequestInit) =>
      init?.method === "PATCH"
        ? new Promise<Response>(() => {})
        : Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    const row = (await screen.findByText("pomodoro")).closest("li")!;
    await userEvent.click(within(row).getByRole("checkbox", { name: "pomodoro" }));

    await waitFor(() =>
      expect(within(row).getByRole("button", { name: "Togli pomodoro dalla lista" }))
        .toBeDisabled()
    );
    expect(within(row).getByRole("checkbox", { name: "pomodoro" })).toBeDisabled();
    const other = screen.getByText("Total 0%").closest("li")!;
    expect(within(other).getByRole("checkbox", { name: "yogurt greco" })).not.toBeDisabled();
  });

  it("un caricamento fallito non viene spacciato per lista vuota", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));
    renderScreen();

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.queryByText(/Lista vuota/)).toBeNull();
  });
});
