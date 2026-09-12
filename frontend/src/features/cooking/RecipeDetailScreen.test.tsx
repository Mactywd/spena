import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { RecipeDetailScreen } from "./RecipeDetailScreen";

const DETAIL = {
  id: "r1", title: "Pasta al pomodoro", description: "Di sempre", source: "manual",
  missing: 1, cookable: false, instructions: "Cuoci.", servings: 2, source_ref: null,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "180 g",
      note: null, availability: "available", satisfied: true },
    { ingredient_id: "i2", ingredient_name: "pomodoro", role: "primary", quantity_text: "400 g",
      note: null, availability: "low", satisfied: false },
    { ingredient_id: "i3", ingredient_name: "aglio", role: "secondary", quantity_text: null,
      note: null, availability: "low", satisfied: true },
  ],
};

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/ricette/r1"]}>
        <Routes>
          <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("RecipeDetailScreen", () => {
  it("distingue ingredienti principali e secondari", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("Principali")).toBeDefined();
    expect(screen.getByText("Secondari")).toBeDefined();
  });

  it("spiega perché un principale quasi finito non basta", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    const row = (await screen.findByText("pomodoro")).closest("li")!;
    expect(row.textContent).toContain("quasi finito, non basta");
  });

  it("un secondario quasi finito è accettato", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DETAIL), { status: 200 })
    ));
    renderScreen();
    const row = (await screen.findByText("aglio")).closest("li")!;
    expect(row.textContent).toContain("quasi finito, basta");
  });

  it("un fallimento nel caricare la ricetta lo dice, non resta a caricare per sempre", async () => {
    // Confondere "carico" con "fallito" lascerebbe lo schermo bloccato su "Carico…"
    // in eterno: l'utente non saprebbe mai che non arriverà nulla.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));
    renderScreen();
    expect(await screen.findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
  });

  it("un fallimento nel caricare la dispensa non apre un foglio di cottura vuoto e muto", async () => {
    // "Cucina" apre CookSheet con le voci di dispensa: se la dispensa non si è
    // caricata, offrire comunque il pulsante produrrebbe un foglio che sembra
    // completo ma non lo è, l'errore travestito da "niente da aggiornare".
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) => {
        if (String(url).includes("/pantry")) {
          return Promise.resolve(new Response("", { status: 500 }));
        }
        return Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }));
      })
    );
    renderScreen();
    expect(await screen.findByText("Principali")).toBeDefined();
    expect(await screen.findByRole("alert")).toHaveTextContent(/dispensa/i);
    expect(screen.queryByRole("button", { name: "Cucina" })).toBeNull();
  });
});
