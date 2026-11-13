import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { createTestQueryClient } from "../../test/queryClient";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { NewMealScreen } from "./NewMealScreen";

type Handler = (url: string, init?: RequestInit) => [unknown, number];

function stubFetch(handler: Handler) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = handler(String(url), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function posts(spy: ReturnType<typeof stubFetch>) {
  return spy.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === "POST")
    .map(([, init]) => JSON.parse(String((init as RequestInit).body)));
}

function renderNew() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <NoticeProvider>
        <MemoryRouter initialEntries={["/pasti/nuovo?giorno=2026-11-10&posto=dinner"]}>
          <Routes>
            <Route path="/pasti/nuovo" element={<NewMealScreen />} />
            <Route path="/pasti" element={<p>la settimana</p>} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("il nuovo pasto", () => {
  it("salva col giorno e il posto dell'indirizzo, poi torna alla settimana", async () => {
    const spy = stubFetch((_url, init) =>
      init?.method === "POST" ? [{ id: "m1" }, 201] : [[], 200]
    );
    renderNew();
    expect(screen.getByRole("heading", { name: "Nuovo pasto" })).toBeInTheDocument();
    expect(screen.getByText("martedì 10 novembre · Cena")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Pasti/ })).toHaveAttribute(
      "href",
      "/pasti?settimana=2026-11-10"
    );
    await userEvent.type(screen.getByLabelText("Piatto"), "Frittata");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    expect(await screen.findByText("la settimana")).toBeInTheDocument();
    expect(screen.getByText("Pasto salvato.")).toBeInTheDocument();
    expect(posts(spy)).toEqual([
      { day: "2026-11-10", slot: "dinner", dish: "Frittata", sides: null, away: false, leftover_of_id: null },
    ]);
  });

  it("su un posto occupato legge l'occupante e «Sostituisci» rimanda con replace", async () => {
    let first = true;
    const spy = stubFetch((_url, init) => {
      if (init?.method !== "POST") return [[], 200];
      if (first) {
        first = false;
        return [{ detail: "C'è già «Pizza» in questo posto.", code: "slot_taken" }, 409];
      }
      return [{ id: "m1" }, 201];
    });
    renderNew();
    await userEvent.type(screen.getByLabelText("Piatto"), "Frittata");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    expect(await screen.findByText("C'è già «Pizza» in questo posto.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sostituisci" }));
    expect(await screen.findByText("la settimana")).toBeInTheDocument();
    const sent = posts(spy);
    expect(sent).toHaveLength(2);
    expect(sent[1]).toMatchObject({ dish: "Frittata", replace: true });
  });

  it("un altro rifiuto mostra il detail del server", async () => {
    stubFetch((_url, init) =>
      init?.method === "POST" ? [{ detail: "Il piatto non può essere vuoto." }, 422] : [[], 200]
    );
    renderNew();
    await userEvent.type(screen.getByLabelText("Piatto"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Il piatto non può essere vuoto.")
    );
  });
});
