import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { createTestQueryClient } from "../../test/queryClient";
import { MemoryRouter } from "react-router-dom";
import { SpendingScreen } from "./SpendingScreen";
import type { DaySpend, Spending, SpendingPeriod } from "./types";

function giorni(primo: string, costi: number[]): DaySpend[] {
  const [anno, mese, giorno] = primo.split("-").map(Number);
  return costi.map((cost_usd, i) => ({
    day: new Date(Date.UTC(anno, mese - 1, giorno + i)).toISOString().slice(0, 10),
    cost_usd,
  }));
}

const MESE: Spending = {
  period: "month",
  first_day: "2026-10-01",
  last_day: "2026-10-13",
  total_usd: 0.025,
  calls: 6,
  unpriced_calls: 1,
  sections: [
    { call_site: "recipe_draft", label: "Ricette scritte con l'AI", cost_usd: 0.021, share: 0.84, calls: 4 },
    {
      call_site: "term_decision",
      label: "Abbinare gli ingredienti dell'import",
      cost_usd: 0.004,
      share: 0.16,
      calls: 2,
    },
  ],
  days: giorni("2026-10-01", [0.004, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.021]),
};

const TRENTA: Spending = { ...MESE, period: "30d", first_day: "2026-09-14", days: giorni("2026-09-14", [...Array(29).fill(0), 0.025]) };

function vuoto(period: SpendingPeriod): Spending {
  return { ...MESE, period, total_usd: 0, calls: 0, unpriced_calls: 0, sections: [], days: giorni("2026-10-13", [0]) };
}

function stubRoutedFetch(route: (path: string) => [unknown, number]) {
  const spy = vi.fn((url: unknown) => {
    const [body, status] = route(String(url));
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

// Il predicato vero di App.tsx, non un `retry: false` di comodo (prima lezione di
// CLAUDE.md); senza attesa fra un tentativo e l'altro, perché il guasto arrivi subito.
function renderScreen() {
  const client = createTestQueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SpendingScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SpendingScreen", () => {
  it("parte da «Questo mese»: lo chiede al server, lo preme, e mostra totale, chiamate, sezioni e giorni", async () => {
    const spy = stubRoutedFetch(() => [MESE, 200]);
    renderScreen();

    expect(screen.getByRole("heading", { name: "Spese dell'AI" })).toBeInTheDocument();
    expect(await screen.findByText("Totale, dall'1 al 13 ottobre")).toBeInTheDocument();
    expect(String(spy.mock.calls[0][0])).toBe("/api/v1/llm-spending?period=month");
    expect(screen.getByRole("button", { name: "Questo mese" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("0,025 $")).toBeInTheDocument();
    expect(screen.getByText("6 chiamate")).toBeInTheDocument();
    expect(
      screen.getByText(
        "1 senza un costo dichiarato da OpenRouter (di solito, una chiamata fallita): non è nel totale."
      )
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Per sezione" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Spesa per sezione" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Per giorno" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /^Costo per giorno/ })).toBeInTheDocument();
  });

  it("un altro periodo si chiede al server, e il suo pulsante si preme", async () => {
    const spy = stubRoutedFetch((path) => [path.includes("period=30d") ? TRENTA : MESE, 200]);
    renderScreen();
    await screen.findByText("Totale, dall'1 al 13 ottobre");

    await userEvent.click(screen.getByRole("button", { name: "Ultimi 30 giorni" }));

    expect(await screen.findByText("Totale, dal 14 settembre al 13 ottobre")).toBeInTheDocument();
    expect(spy.mock.calls.map(([url]) => String(url))).toContain("/api/v1/llm-spending?period=30d");
    expect(screen.getByRole("button", { name: "Ultimi 30 giorni" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Questo mese" })).toHaveAttribute("aria-pressed", "false");
  });

  it.each([
    ["month", "Questo mese", "Nessuna chiamata all'AI questo mese."],
    ["30d", "Ultimi 30 giorni", "Nessuna chiamata all'AI negli ultimi 30 giorni."],
    ["all", "Da sempre", "Nessuna chiamata all'AI, finora."],
  ] as const)("senza chiamate (%s) una frase, nessun grafico, e i periodi restano", async (period, pulsante, frase) => {
    stubRoutedFetch((path) => [vuoto(path.includes(`period=${period}`) ? period : "month"), 200]);
    renderScreen();
    await screen.findByText("Nessuna chiamata all'AI questo mese.");

    await userEvent.click(screen.getByRole("button", { name: pulsante }));

    expect(await screen.findByText(frase)).toBeInTheDocument();
    expect(screen.queryByText(/^Totale,/)).toBeNull();
    expect(screen.queryByRole("img")).toBeNull();
    expect(within(screen.getByRole("group", { name: "Periodo" })).getAllByRole("button")).toHaveLength(3);
  });

  it("la chat dei piatti è una sezione come le altre", async () => {
    const conPasti: Spending = {
      ...MESE,
      total_usd: 0.325,
      calls: 9,
      sections: [
        { call_site: "meal_chat", label: "Chat dei piatti", cost_usd: 0.3, share: 0.9231, calls: 3 },
        ...MESE.sections,
      ],
    };
    stubRoutedFetch(() => [conPasti, 200]);
    renderScreen();

    expect(await screen.findByText("Chat dei piatti")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Per sezione" })).toBeInTheDocument();
    expect(screen.queryByText("Claude")).toBeNull();
  });

  it("solo chiamate senza costo: il totale a zero, la riga che lo dice, nessun grafico", async () => {
    const senzaCosto: Spending = {
      ...MESE,
      total_usd: 0,
      calls: 2,
      unpriced_calls: 2,
      sections: [{ call_site: "recipe_draft", label: "Ricette scritte con l'AI", cost_usd: 0, share: 0, calls: 2 }],
      days: giorni("2026-10-01", Array(13).fill(0)),
    };
    stubRoutedFetch(() => [senzaCosto, 200]);
    renderScreen();

    expect(await screen.findByText("0,00 $")).toBeInTheDocument();
    expect(screen.getByText("2 chiamate")).toBeInTheDocument();
    expect(
      screen.getByText(
        "2 senza un costo dichiarato da OpenRouter (di solito, chiamate fallite): non sono nel totale."
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Per sezione" })).toBeNull();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("la riga delle chiamate senza costo c'è solo se ce n'è almeno una", async () => {
    stubRoutedFetch(() => [{ ...MESE, unpriced_calls: 0 }, 200]);
    renderScreen();
    await screen.findByText("0,025 $");

    expect(screen.queryByText(/senza un costo dichiarato/)).toBeNull();
  });

  it("il server che non risponde: lo dice, e «Riprova» richiede", async () => {
    const spy = stubRoutedFetch(() => [{ detail: "rotto" }, 500]);
    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a leggere le spese.");
    const prima = spy.mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));

    await waitFor(() => expect(spy.mock.calls.length).toBeGreaterThan(prima));
  });

  it("i tre periodi sono un gruppo, nell'ordine deciso", async () => {
    stubRoutedFetch(() => [MESE, 200]);
    renderScreen();

    const gruppo = screen.getByRole("group", { name: "Periodo" });
    expect(within(gruppo).getAllByRole("button").map((pulsante) => pulsante.textContent)).toEqual([
      "Questo mese",
      "Ultimi 30 giorni",
      "Da sempre",
    ]);
    await screen.findByText("0,025 $");
  });
});
