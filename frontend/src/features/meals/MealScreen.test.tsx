import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { createTestQueryClient } from "../../test/queryClient";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { MealScreen } from "./MealScreen";
import type { Meal } from "../../domain/types";

function meal(extra: Partial<Meal> = {}): Meal {
  return {
    id: "m1", day: "2026-11-10", slot: "dinner", week: "2026-11-09", dish: "Pollo arrosto",
    sides: "piadina · banana", away: false, status: "official", unrecorded: false,
    recipe: null, leftover_of: null, ...extra,
  };
}

type Handler = (url: string, init?: RequestInit) => [unknown, number];

function stubFetch(handler: Handler) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = handler(String(url), init);
    return Promise.resolve(
      status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status })
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function calls(spy: ReturnType<typeof stubFetch>, method: string) {
  return spy.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === method)
    .map(([url, init]) => ({ url: String(url), body: (init as RequestInit).body ? JSON.parse(String((init as RequestInit).body)) : null }));
}

function renderMeal() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <NoticeProvider>
        <MemoryRouter initialEntries={["/pasti/m1"]}>
          <Routes>
            <Route path="/pasti" element={<p>la settimana</p>} />
            <Route path="/pasti/:id" element={<MealScreen />} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

const reads = (m: Meal): Handler => (_url, init) => (init?.method ? [m, 200] : [m, 200]);

afterEach(() => vi.unstubAllGlobals());

describe("la schermata del piatto", () => {
  it("mostra posto, piatto e accompagnamenti", async () => {
    stubFetch(reads(meal()));
    renderMeal();
    expect(await screen.findByRole("heading", { level: 1, name: "Pollo arrosto" })).toBeInTheDocument();
    expect(screen.getByText("martedì 10 novembre · Cena")).toBeInTheDocument();
    expect(screen.getByText("piadina · banana")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Pasti/ })).toHaveAttribute("href", "/pasti?settimana=2026-11-09");
  });

  it("«Correggi» con il giorno cambiato manda solo `day` e chiude il modulo", async () => {
    const spy = stubFetch(reads(meal()));
    renderMeal();
    await userEvent.click(await screen.findByRole("button", { name: "Correggi" }));
    const day = screen.getByLabelText("Giorno");
    fireEvent.change(day, { target: { value: "2026-11-12" } });
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));
    await vi.waitFor(() => expect(calls(spy, "PATCH")).toHaveLength(1));
    expect(calls(spy, "PATCH")[0].body).toEqual({ day: "2026-11-12" });
    await vi.waitFor(() => expect(screen.queryByLabelText("Giorno")).toBeNull());
  });

  it("spostare su un posto occupato chiede «Sostituisci» e rimanda con replace", async () => {
    let first = true;
    const spy = stubFetch((_url, init) => {
      if (init?.method !== "PATCH") return [meal(), 200];
      if (first) {
        first = false;
        return [{ detail: "C'è già «Pizza» in questo posto.", code: "slot_taken" }, 409];
      }
      return [meal({ slot: "lunch" }), 200];
    });
    renderMeal();
    await userEvent.click(await screen.findByRole("button", { name: "Correggi" }));
    await userEvent.selectOptions(screen.getByLabelText("Pasto"), "lunch");
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));
    expect(await screen.findByText("C'è già «Pizza» in questo posto.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sostituisci" }));
    await vi.waitFor(() => expect(calls(spy, "PATCH")).toHaveLength(2));
    expect(calls(spy, "PATCH")[1].body).toEqual({ slot: "lunch", replace: true });
  });

  it("«Elimina» con una ricetta fuori dal ricettario lo dice, poi torna alla settimana", async () => {
    const spy = stubFetch((_url, init) =>
      init?.method === "DELETE" ? [null, 204] : [meal({ recipe: { id: "r1", title: "Pollo", in_book: false } }), 200]
    );
    renderMeal();
    await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));
    expect(screen.getByText("Eliminare «Pollo arrosto»?")).toBeInTheDocument();
    expect(screen.getByText("La sua ricetta non è nel ricettario: si elimina con il pasto.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sì, elimina" }));
    expect(await screen.findByText("la settimana")).toBeInTheDocument();
    expect(screen.getByText("Pasto eliminato.")).toBeInTheDocument();
    expect(calls(spy, "DELETE")).toHaveLength(1);
  });

  it("una ricetta nel ricettario non porta la frase della ricetta", async () => {
    stubFetch(reads(meal({ recipe: { id: "r1", title: "Pollo", in_book: true } })));
    renderMeal();
    await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));
    expect(screen.queryByText(/non è nel ricettario/)).toBeNull();
  });

  it("una bozza ha «Rendi ufficiale», che manda `status: official`", async () => {
    const spy = stubFetch(reads(meal({ status: "draft" })));
    renderMeal();
    expect(await screen.findByText("È una bozza: la ricetta arriva quando diventa ufficiale.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Rendi ufficiale" }));
    await vi.waitFor(() => expect(calls(spy, "PATCH")).toHaveLength(1));
    expect(calls(spy, "PATCH")[0].body).toEqual({ status: "official" });
  });

  it("un pasto ufficiale senza ricetta offre le due strade; fuori casa nessuna", async () => {
    stubFetch(reads(meal()));
    const first = renderMeal();
    expect(await screen.findByText("Questo pasto non ha ancora una ricetta.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Scrivi la ricetta" })).toHaveAttribute("href", "/pasti/m1/ricetta/nuova");
    expect(screen.getByRole("link", { name: "Scegli dal ricettario" })).toHaveAttribute("href", "/pasti/m1/ricetta/scegli");
    first.unmount();

    stubFetch(reads(meal({ away: true })));
    renderMeal();
    expect(await screen.findByText("Fuori casa: non c'è niente da cucinare.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Scrivi la ricetta" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Scegli dal ricettario" })).toBeNull();
    expect(within(document.body).queryByText("Scegli dal ricettario")).toBeNull();
  });
});
