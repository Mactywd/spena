import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ConnectScreen } from "./ConnectScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { Activity } from "./types";

const CHIAVE = "k".repeat(43);

const SENZA_CHIAVE: Activity = {
  today: "2026-10-13",
  last_sync: null,
  steps_days: [],
  exercises: [],
  weights: [],
  connection: {
    has_token: false,
    created_day: null,
    created_time: null,
    last_used_day: null,
    last_used_time: null,
  },
};

const CON_CHIAVE: Activity = {
  ...SENZA_CHIAVE,
  connection: {
    has_token: true,
    created_day: "2026-10-13",
    created_time: "14:00",
    last_used_day: "2026-10-13",
    last_used_time: "14:05",
  },
};

function stubRoutedFetch(route: (path: string, init?: RequestInit) => [unknown, number]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function conChiaveNuova(attivita: Activity, statoChiave = 201) {
  return stubRoutedFetch((path, init) =>
    path === "/api/v1/activity/token" && init?.method === "POST"
      ? [{ token: CHIAVE, header: "X-Spena-Token" }, statoChiave]
      : [attivita, 200]
  );
}

// Il predicato vero di App.tsx, non un `retry: false` di comodo (prima lezione di
// CLAUDE.md); senza attesa fra un tentativo e l'altro.
function renderScreen() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate, retryDelay: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ConnectScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ConnectScreen", () => {
  it("senza chiave la spiega e la crea; la chiave e le intestazioni si vedono subito", async () => {
    const spy = conChiaveNuova(SENZA_CHIAVE);
    renderScreen();

    expect(
      await screen.findByText(
        "Spena accetta i dati solo da chi porta la sua chiave. Creala, poi incollala in HC Webhook come dicono i passi qui sotto."
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText("Le intestazioni da incollare compaiono qui quando crei la chiave.")
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Crea la chiave" }));

    expect(
      await screen.findByText("Ecco la chiave. Si vede solo adesso: copiala in HC Webhook prima di uscire da qui.")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Chiave")).toHaveValue(CHIAVE);
    expect(screen.getByLabelText("Intestazioni (JSON)")).toHaveValue(`{"X-Spena-Token":"${CHIAVE}"}`);
    expect(spy.mock.calls.some(([url, init]) => String(url) === "/api/v1/activity/token" && init?.method === "POST")).toBe(true);
  });

  it("l'indirizzo c'è sempre, con l'origine della pagina", async () => {
    conChiaveNuova(SENZA_CHIAVE);
    renderScreen();

    expect(screen.getByLabelText("Indirizzo")).toHaveValue(
      `${window.location.origin}/api/v1/activity/hc-webhook`
    );
    await screen.findByRole("button", { name: "Crea la chiave" });
  });

  it("con una chiave: quando è nata e quando è stata usata; rigenerarla chiede conferma", async () => {
    conChiaveNuova(CON_CHIAVE);
    renderScreen();

    expect(
      await screen.findByText("Chiave creata oggi alle 14:00. Usata l'ultima volta oggi alle 14:05.")
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Rigenera la chiave" }));
    expect(
      screen.getByText("La chiave di adesso smetterà di funzionare, e in HC Webhook andrà incollata quella nuova.")
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("button", { name: "Rigenera la chiave" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Rigenera la chiave" }));
    await userEvent.click(screen.getByRole("button", { name: "Rigenera" }));
    expect(await screen.findByLabelText("Chiave")).toHaveValue(CHIAVE);
  });

  it("la creazione che non riesce lo dice, e il pulsante resta", async () => {
    conChiaveNuova(SENZA_CHIAVE, 500);
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Crea la chiave" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a creare la chiave.");
    expect(screen.getByRole("button", { name: "Crea la chiave" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Chiave")).toBeNull();
  });

  it("l'errore di una rigenerazione che non è riuscita si toglie con «Annulla»", async () => {
    conChiaveNuova(CON_CHIAVE, 500);
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Rigenera la chiave" }));
    await userEvent.click(screen.getByRole("button", { name: "Rigenera" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a creare la chiave.");

    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("lo stato della chiave che non si legge: lo dice, e «Riprova» richiede", async () => {
    const spy = stubRoutedFetch(() => [{ detail: "rotto" }, 500]);
    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a leggere la chiave.");
    const prima = spy.mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    await waitFor(() => expect(spy.mock.calls.length).toBeGreaterThan(prima));
  });

  it("i passi sono dieci, nell'ordine, e il ritorno porta ad «Attività»", async () => {
    conChiaveNuova(SENZA_CHIAVE);
    renderScreen();

    const passi = within(screen.getByRole("list", { name: "I passi in HC Webhook" })).getAllByRole("listitem");
    expect(passi).toHaveLength(10);
    expect(passi[0]).toHaveTextContent("In Samsung Health: Impostazioni › Health Connect.");
    expect(passi[3]).toHaveTextContent("Alla voce «Risoluzione passi» lascia «Giornaliero»");
    expect(passi[7]).toHaveTextContent("Tocca «Testa Webhook»");
    expect(screen.getByRole("link", { name: "Attività" })).toHaveAttribute("href", "/attivita");
    await screen.findByRole("button", { name: "Crea la chiave" });
  });
});
