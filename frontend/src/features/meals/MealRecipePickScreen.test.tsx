import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { createTestQueryClient } from "../../test/queryClient";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { MealRecipePickScreen } from "./MealRecipePickScreen";

const R = (id: string, title: string) => ({
  id, title, cookable: true, missing: 0, missing_names: [], image_url: null, category: null,
  cost: null, prep_minutes: null, cook_minutes: null, description: null, source: "manual",
});

function stubFetch(copyStatus = 200) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    if (init?.method === "POST")
      return Promise.resolve(
        new Response(JSON.stringify(copyStatus === 200 ? { id: "m1" } : { detail: "Il pasto ha già una ricetta." }), { status: copyStatus })
      );
    if (path.includes("q=frittata"))
      return Promise.resolve(new Response(JSON.stringify([R("r9", "Frittata di zucchine")]), { status: 200 }));
    return Promise.resolve(new Response(JSON.stringify([R("r1", "Pasta")]), { status: 200 }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderPick() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <NoticeProvider>
        <MemoryRouter initialEntries={["/pasti/m1/ricetta/scegli"]}>
          <Routes>
            <Route path="/pasti/:id/ricetta/scegli" element={<MealRecipePickScreen />} />
            <Route path="/pasti/:id" element={<p>il pasto</p>} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("scegliere la ricetta di un pasto", () => {
  it("cerca e mostra i titoli", async () => {
    const spy = stubFetch();
    renderPick();
    expect(await screen.findByText("Pasta")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Cerca nel ricettario"), "frittata");
    expect(await screen.findByText("Frittata di zucchine")).toBeInTheDocument();
    expect(spy.mock.calls.some(([u]) => String(u).startsWith("/api/v1/recipes/search?q=frittata"))).toBe(true);
  });

  it("un tocco copia la ricetta nel pasto e torna al pasto", async () => {
    const spy = stubFetch();
    renderPick();
    await userEvent.type(screen.getByLabelText("Cerca nel ricettario"), "frittata");
    await userEvent.click(await screen.findByRole("button", { name: /Frittata di zucchine/ }));
    expect(await screen.findByText("il pasto")).toBeInTheDocument();
    expect(screen.getByText("Ricetta copiata nel pasto.")).toBeInTheDocument();
    const post = spy.mock.calls.find(([, init]) => init?.method === "POST")!;
    expect(String(post[0])).toBe("/api/v1/meals/m1/recipe/copy");
    expect(JSON.parse(String(post[1]!.body))).toEqual({ recipe_id: "r9" });
  });

  it("un rifiuto mostra il detail del server", async () => {
    stubFetch(409);
    renderPick();
    await userEvent.click(await screen.findByRole("button", { name: /Pasta/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Il pasto ha già una ricetta.");
  });
});
