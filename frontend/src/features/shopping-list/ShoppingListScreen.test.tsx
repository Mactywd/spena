import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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
    expect(await screen.findByTitle("rientrata perché finita cucinando")).toBeDefined();
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
    expect(await screen.findByRole("link", { name: "Sistema la spesa" })).toBeDefined();
  });
});
