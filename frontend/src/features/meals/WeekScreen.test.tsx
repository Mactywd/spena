import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { createTestQueryClient } from "../../test/queryClient";
import { WeekScreen } from "./WeekScreen";
import { pollWhilePreparing } from "./api";
import type { Meal, MealSlot, MealWeek } from "../../domain/types";

function meal(id: string, day: string, slot: MealSlot, extra: Partial<Meal> = {}): Meal {
  return {
    id, day, slot, week: "2025-11-10", dish: `piatto ${id}`, sides: null, away: false,
    status: "official", unrecorded: false, recipe: null, leftover_of: null, ...extra,
  };
}

const DAYS = ["10", "11", "12", "13", "14", "15", "16"].map((d) => `2025-11-${d}`);
const WEEK: MealWeek = {
  monday: "2025-11-10", sunday: "2025-11-16", today: "2025-11-12",
  previous: "2025-11-03", next: "2025-11-17", days: DAYS,
  meals: [
    meal("m1", "2025-11-10", "dinner", { dish: "Pollo arrosto", sides: "piadina · banana" }),
    meal("m2", "2025-11-11", "lunch", { dish: "Pizza", away: true }),
    meal("m3", "2025-11-11", "dinner", { dish: "Riso", status: "draft", unrecorded: true }),
    meal("m4", "2025-11-12", "lunch", {
      dish: "Pollo di ieri",
      leftover_of: { id: "m1", day: "2025-11-10", slot: "dinner", dish: "Pollo arrosto", recipe_id: null },
    }),
  ],
};

// Le schede dei cambi da applicare in testa alla settimana (piano 6c) hanno la loro GET:
// risponde qui, vuota se il test non ne chiede, così `handler` vede solo la settimana
function stubFetch(
  handler: (path: string) => [unknown, number] = () => [WEEK, 200],
  pendingCards: unknown[] = []
) {
  const spy = vi.fn((url: unknown) => {
    const [body, status] = String(url).includes("/change-cards")
      ? [pendingCards, 200]
      : handler(String(url));
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderWeek(start = "/pasti") {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter initialEntries={[start]}>
        <Routes>
          <Route path="/pasti" element={<WeekScreen />} />
          <Route path="/pasti/nuovo" element={<p>modulo</p>} />
          <Route path="/pasti/pianifica" element={<p>pianificazione</p>} />
          <Route path="/pasti/:id" element={<p>piatto</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("la settimana", () => {
  it("mostra sette giorni da lunedì, con pranzo e cena", async () => {
    stubFetch();
    renderWeek();
    await screen.findByText("Lunedì 10");
    for (const label of ["Martedì 11", "Mercoledì 12", "Giovedì 13", "Venerdì 14", "Sabato 15", "Domenica 16"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getAllByText("Pranzo")).toHaveLength(7);
    expect(screen.getAllByText("Cena")).toHaveLength(7);
    // «Pianifica con Claude» (piano 6c) porta a `/pasti/pianifica`: non è un posto
    const places = screen.getAllByRole("link").filter(
      (a) => a.getAttribute("href")?.startsWith("/pasti/") && a.getAttribute("href") !== "/pasti/pianifica"
    );
    expect(places).toHaveLength(14);
    expect(screen.getAllByText("+ da pianificare")).toHaveLength(10);
  });

  it("un pasto con la ricetta in preparazione lo dice, e la settimana si rilegge finché dura", async () => {
    const preparing = {
      ...WEEK,
      preparing: true,
      meals: [meal("m1", "2025-11-10", "dinner", { dish: "Pollo arrosto", recipe_state: "preparing" })],
    };
    stubFetch(() => [preparing, 200]);
    renderWeek();
    expect(await screen.findByText("Ricetta in preparazione")).toBeInTheDocument();
  });

  it("la rilettura ogni 3 s dura solo finché c'è una ricetta in preparazione", () => {
    expect(pollWhilePreparing(true)).toBe(3000);
    expect(pollWhilePreparing(false)).toBe(false);
    expect(pollWhilePreparing(undefined)).toBe(false);
  });

  it("oggi è evidenziato", async () => {
    stubFetch();
    renderWeek();
    await screen.findByText("Lunedì 10");
    const today = document.querySelector('[aria-current="date"]') as HTMLElement;
    expect(today).toHaveTextContent("Mercoledì 12");
    expect(today).toHaveTextContent("oggi");
  });

  it("un posto vuoto porta al modulo", async () => {
    stubFetch();
    renderWeek();
    await screen.findByText("Lunedì 10");
    expect(screen.getAllByText("+ da pianificare")[0].closest("a")).toHaveAttribute(
      "href",
      "/pasti/nuovo?giorno=2025-11-10&posto=lunch"
    );
  });

  it("un pasto mostra piatto, accompagnamenti e segni", async () => {
    stubFetch();
    renderWeek();
    const link = (await screen.findByText("Pollo arrosto")).closest("a")!;
    expect(link).toHaveAttribute("href", "/pasti/m1");
    expect(within(link).getByText("piadina · banana")).toBeInTheDocument();
    expect(screen.getByText("Fuori casa")).toBeInTheDocument();
    expect(screen.getByText("Non registrata")).toBeInTheDocument();
    expect(screen.queryByText("Bozza")).not.toBeInTheDocument();
    expect(screen.getByText("Avanzo")).toBeInTheDocument();
  });

  it("le frecce cambiano settimana", async () => {
    const spy = stubFetch((path) =>
      [path.includes("of=2025-11-17") ? { ...WEEK, monday: "2025-11-17", sunday: "2025-11-23", meals: [] } : WEEK, 200]
    );
    renderWeek();
    await screen.findByText("Lunedì 10");
    expect(screen.queryByText("Torna a oggi")).not.toBeInTheDocument();
    const next = screen.getByRole("link", { name: "Settimana dopo" });
    expect(next).toHaveAttribute("href", "/pasti?settimana=2025-11-17");
    await userEvent.click(next);
    await screen.findByText("Torna a oggi");
    expect(spy.mock.calls.some(([u]) => String(u).includes("of=2025-11-17"))).toBe(true);
  });

  it("un errore offre Riprova", async () => {
    // il client dell'app riprova due volte prima di arrendersi: i primi tre tentativi cadono
    let calls = 0;
    const spy = stubFetch(() => (++calls <= 3 ? [{ detail: "x" }, 500] : [WEEK, 200]));
    renderWeek();
    await userEvent.click(await screen.findByRole("button", { name: "Riprova" }));
    // le letture della settimana: quella delle schede dei cambi non conta
    const weekCalls = () => spy.mock.calls.filter(([u]) => !String(u).includes("/change-cards"));
    await waitFor(() => expect(weekCalls().length).toBeGreaterThanOrEqual(4));
    await screen.findByText("Lunedì 10");
  });
  it("in fondo «Pianifica con Claude»; in testa le schede dei cambi da applicare", async () => {
    stubFetch(undefined, [
      {
        id: "c1", kind: "forward", status: "proposed", list_only: false,
        title: "Cambi per la cena di martedì", meals: [], rows: [],
        created_at: "2025-11-11T10:00:00Z", applied_at: null,
      },
    ]);
    renderWeek();
    await screen.findByText("Lunedì 10");
    expect(await screen.findByText("Schede dei cambi da applicare")).toBeInTheDocument();
    expect(screen.getByText("Cambi per la cena di martedì")).toBeInTheDocument();
    const plan = screen.getByRole("link", { name: "Pianifica con Claude" });
    expect(plan).toHaveAttribute("href", "/pasti/pianifica");
    await userEvent.click(plan);
    expect(await screen.findByText("pianificazione")).toBeInTheDocument();
  });
});
