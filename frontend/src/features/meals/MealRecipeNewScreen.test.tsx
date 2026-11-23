import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { createTestQueryClient } from "../../test/queryClient";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { MealRecipeNewScreen } from "./MealRecipeNewScreen";

const MEAL = { id: "m1", dish: "Frittata", week: "2026-11-09", day: "2026-11-10", slot: "dinner" };

function stubFetch() {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    if (init?.method === "POST") return Promise.resolve(new Response(JSON.stringify({ id: "r5" }), { status: 201 }));
    if (path.includes("/meals/m1")) return Promise.resolve(new Response(JSON.stringify(MEAL), { status: 200 }));
    return Promise.resolve(new Response("[]", { status: 200 }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderNew() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <NoticeProvider>
        <MemoryRouter initialEntries={["/pasti/m1/ricetta/nuova"]}>
          <Routes>
            <Route path="/pasti/:id/ricetta/nuova" element={<MealRecipeNewScreen />} />
            <Route path="/pasti/:id" element={<p>il pasto</p>} />
            <Route path="/ricette/:rid" element={<p>la ricetta r9</p>} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("la ricetta scritta per un pasto", () => {
  it("il titolo vale il piatto e le porzioni 1", async () => {
    stubFetch();
    renderNew();
    expect(await screen.findByDisplayValue("Frittata")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Scrivi la ricetta" })).toBeInTheDocument();
    expect(screen.getByText("Resta fuori dal ricettario finché non la salvi lì.")).toBeInTheDocument();
    expect(screen.getByLabelText(/Porzioni/)).toHaveValue("1");
    expect(screen.getByRole("link", { name: /Pasto/ })).toHaveAttribute("href", "/pasti/m1");
  });

  it("«Salva la ricetta» manda meal_id e source manual, poi torna al pasto", async () => {
    const spy = stubFetch();
    renderNew();
    await screen.findByDisplayValue("Frittata");
    await userEvent.type(screen.getByLabelText(/Procedimento/), "Sbatti le uova.");
    await userEvent.click(screen.getByRole("button", { name: "Salva la ricetta" }));
    expect(await screen.findByText("il pasto")).toBeInTheDocument();
    expect(screen.getByText("Salvata.")).toBeInTheDocument();
    const post = spy.mock.calls.find(([, init]) => init?.method === "POST")!;
    expect(String(post[0])).toBe("/api/v1/recipes");
    const body = JSON.parse(String(post[1]!.body));
    expect(body.meal_id).toBe("m1");
    expect(body.source).toBe("manual");
    expect(body.title).toBe("Frittata");
  });

  function stubConflict(code: string) {
    const posts: Array<Record<string, unknown>> = [];
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      const path = String(url);
      if (init?.method === "POST") {
        posts.push(JSON.parse(String(init.body)));
        if (posts.length === 1) {
          return Promise.resolve(
            new Response(JSON.stringify({ code, detail: "Il pasto ha già una ricetta." }), { status: 409 })
          );
        }
        return Promise.resolve(new Response(JSON.stringify({ id: "r9" }), { status: 201 }));
      }
      if (path.includes("/meals/m1")) return Promise.resolve(new Response(JSON.stringify(MEAL), { status: 200 }));
      return Promise.resolve(new Response("[]", { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    return posts;
  }

  it("se intanto arriva la ricetta di Claude, si salva nel ricettario", async () => {
    const posts = stubConflict("has_recipe");
    renderNew();
    await screen.findByDisplayValue("Frittata");
    await userEvent.type(screen.getByLabelText(/Procedimento/), "Sbatti le uova.");
    await userEvent.click(screen.getByRole("button", { name: "Salva la ricetta" }));
    expect(
      await screen.findByText(
        "Nel frattempo è arrivata la ricetta di Claude. Quella che hai scritto non è persa: puoi salvarla nel ricettario."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Il pasto ha già una ricetta.")).toBeInTheDocument();
    expect(screen.getByLabelText(/Procedimento/)).toHaveValue("Sbatti le uova.");
    expect(screen.getByRole("link", { name: "Vedi la ricetta di Claude" })).toHaveAttribute("href", "/pasti/m1");
    await userEvent.click(screen.getByRole("button", { name: "Salva nel ricettario" }));
    expect(await screen.findByText("la ricetta r9")).toBeInTheDocument();
    expect(screen.getByText("Salvata nel ricettario.")).toBeInTheDocument();
    expect(posts).toHaveLength(2);
    expect(posts[1]).toEqual({ ...posts[0], meal_id: null });
  });

  it("un 409 con un altro code non mostra l'avviso", async () => {
    stubConflict("altro");
    renderNew();
    await screen.findByDisplayValue("Frittata");
    await userEvent.type(screen.getByLabelText(/Procedimento/), "Sbatti le uova.");
    await userEvent.click(screen.getByRole("button", { name: "Salva la ricetta" }));
    expect(await screen.findByText("Il pasto ha già una ricetta.")).toBeInTheDocument();
    expect(screen.queryByText(/Nel frattempo è arrivata/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Salva nel ricettario" })).not.toBeInTheDocument();
  });

  function stubReplace(undo: Response | null) {
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      const path = String(url);
      if (init?.method === "POST" && path.endsWith("/undo")) {
        return Promise.resolve(undo ?? new Response("{}", { status: 200 }));
      }
      if (init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ id: "r5", undo_change_id: "c7" }), { status: 201 }));
      }
      if (path.includes("/meals/m1")) return Promise.resolve(new Response(JSON.stringify(MEAL), { status: 200 }));
      return Promise.resolve(new Response("[]", { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    return spy;
  }

  async function saveReplacing() {
    renderNew();
    await screen.findByDisplayValue("Frittata");
    await userEvent.type(screen.getByLabelText(/Procedimento/), "Sbatti le uova.");
    await userEvent.click(screen.getByRole("button", { name: "Salva la ricetta" }));
    expect(await screen.findByText("il pasto")).toBeInTheDocument();
  }

  it("salvata al posto di quella di Claude, con Annulla", async () => {
    stubReplace(null);
    await saveReplacing();
    expect(screen.getByText("Salvata al posto di quella di Claude.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Annulla" })).toBeInTheDocument();
  });

  it("Annulla rimette quella di Claude", async () => {
    const spy = stubReplace(null);
    await saveReplacing();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(await screen.findByText("Rimessa la ricetta di Claude.")).toBeInTheDocument();
    const undo = spy.mock.calls.find(([u]) => String(u) === "/api/v1/meals/m1/chat/changes/c7/undo")!;
    expect(undo[1]?.method).toBe("POST");
  });

  it("un Annulla rifiutato dice perché", async () => {
    stubReplace(
      new Response(JSON.stringify({ code: "change_stale", detail: "La ricetta è cambiata dopo." }), { status: 409 })
    );
    await saveReplacing();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(await screen.findByText("La ricetta è cambiata dopo.")).toBeInTheDocument();
  });

  it("senza sostituzione resta Salvata.", async () => {
    stubFetch();
    await saveReplacing();
    expect(screen.getByText("Salvata.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Annulla" })).not.toBeInTheDocument();
  });
});
