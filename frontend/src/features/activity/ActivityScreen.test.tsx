import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ActivityScreen } from "./ActivityScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { Activity } from "./types";

const GIORNI = ["2026-10-13", "2026-10-12", "2026-10-11", "2026-10-10", "2026-10-09", "2026-10-08", "2026-10-07"];

const CON_DATI: Activity = {
  today: "2026-10-13",
  last_sync: {
    day: "2026-10-13",
    time: "14:05",
    status: "ok",
    stale: false,
    steps_days: 1,
    exercises: 1,
    weights: 1,
    ignored: [],
    problems: [],
  },
  steps_days: GIORNI.map((day, i) => ({ day, steps: i === 0 ? 8421 : i === 2 ? 12345 : null })),
  exercises: [
    {
      day: "2026-10-13",
      time: "18:00",
      label: "Corsa",
      title: "Giro del parco",
      minutes: 32,
      distance_km: 5.1,
      source: "Samsung Health",
    },
  ],
  weights: [{ day: "2026-10-13", time: "07:30", kilograms: 72.4 }],
  connection: {
    has_token: true,
    created_day: "2026-10-12",
    created_time: "21:00",
    last_used_day: "2026-10-13",
    last_used_time: "14:05",
  },
};

function stubFetch(body: unknown, status = 200) {
  const spy = vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status })));
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderScreen() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate, retryDelay: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ActivityScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ActivityScreen", () => {
  it("mostra l'ultima sincronizzazione, i passi dei 7 giorni, gli allenamenti e le pesate", async () => {
    stubFetch(CON_DATI);
    renderScreen();

    expect(screen.getByRole("heading", { name: "Attività", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText("Ultima sincronizzazione: oggi alle 14:05.")).toBeInTheDocument();

    const passi = within(screen.getByRole("list", { name: "Passi degli ultimi 7 giorni" })).getAllByRole("listitem");
    expect(passi).toHaveLength(7);
    expect(passi[0]).toHaveTextContent("Oggi8.421");
    expect(passi[1]).toHaveTextContent("Ierinessun dato");
    expect(passi[2]).toHaveTextContent("dom 11 ott12.345");

    const allenamenti = screen.getByRole("list", { name: "Allenamenti degli ultimi 7 giorni" });
    expect(within(allenamenti).getByText("Corsa («Giro del parco») · 32 min · 5,1 km")).toBeInTheDocument();
    expect(within(allenamenti).getByText("Oggi, 18:00 · Samsung Health")).toBeInTheDocument();

    const pesate = screen.getByRole("list", { name: "Ultime pesate" });
    expect(within(pesate).getByText("72,4 kg")).toBeInTheDocument();
    expect(within(pesate).getByText("Oggi, 07:30")).toBeInTheDocument();

    expect(screen.getByRole("link", { name: "Collegamento con HC Webhook" })).toHaveAttribute(
      "href",
      "/attivita/collega"
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("mai sincronizzato: dice cosa manca e porta al collegamento", async () => {
    stubFetch({ ...CON_DATI, last_sync: null, exercises: [], weights: [] });
    renderScreen();

    expect(await screen.findByRole("heading", { name: "Nessun dato da Health Connect, per ora" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Collega HC Webhook" })).toHaveAttribute("href", "/attivita/collega");
    expect(screen.queryByRole("heading", { name: "Passi" })).toBeNull();
  });

  it("la prova di HC Webhook si riconosce", async () => {
    stubFetch({ ...CON_DATI, last_sync: { ...CON_DATI.last_sync!, status: "test" } });
    renderScreen();

    expect(
      await screen.findByText(
        "Ultima sincronizzazione: oggi alle 14:05, la prova di HC Webhook: arrivata, e non salva niente."
      )
    ).toBeInTheDocument();
  });

  it("un rifiuto vecchio: il perché, e l'avviso sulla batteria", async () => {
    stubFetch({
      ...CON_DATI,
      last_sync: {
        ...CON_DATI.last_sync!,
        day: "2026-10-11",
        time: "09:10",
        status: "rejected",
        stale: true,
        problems: ["Rifiutato: il corpo non è JSON."],
      },
    });
    renderScreen();

    expect(await screen.findByText("Ultima sincronizzazione: 11 ottobre alle 09:10, rifiutata.")).toBeInTheDocument();
    const avvisi = screen.getAllByRole("alert").map((avviso) => avviso.textContent);
    expect(avvisi).toEqual([
      "Da più di un giorno non arriva niente. Controlla che HC Webhook non sia limitato dall'ottimizzazione della batteria, e prova «Sincronizza ora».",
      "Rifiutato: il corpo non è JSON.",
    ]);
  });

  it("i tipi arrivati e non usati si nominano", async () => {
    stubFetch({ ...CON_DATI, last_sync: { ...CON_DATI.last_sync!, ignored: ["frequenza cardiaca", "sonno"] } });
    renderScreen();

    expect(
      await screen.findByText(
        "Arrivati e non usati: frequenza cardiaca, sonno. Nel webhook di Spena, in HC Webhook, si possono togliere."
      )
    ).toBeInTheDocument();
  });

  it("senza allenamenti né pesate lo dice", async () => {
    stubFetch({ ...CON_DATI, exercises: [], weights: [] });
    renderScreen();

    expect(await screen.findByText("Nessun allenamento negli ultimi 7 giorni.")).toBeInTheDocument();
    expect(screen.getByText("Nessuna pesata, per ora.")).toBeInTheDocument();
  });

  it("il server che non risponde: lo dice, e «Riprova» richiede", async () => {
    const spy = stubFetch({ detail: "rotto" }, 500);
    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a leggere l'attività.");
    const prima = spy.mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    await waitFor(() => expect(spy.mock.calls.length).toBeGreaterThan(prima));
  });
});
