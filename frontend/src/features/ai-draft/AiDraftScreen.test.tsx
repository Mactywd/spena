import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AiDraftScreen } from "./AiDraftScreen";

const DRAFT = {
  title: "Pasta al pomodoro", description: "Svelta",
  instructions: "1. Cuoci.", servings: 2,
  ingredients: [
    { raw_name: "pasta", role: "primary", quantity_text: "180 g", ingredient_id: "i1",
      matched_name: "pasta", confident: true },
    { raw_name: "basilico fresco", role: "secondary", quantity_text: "q.b.",
      ingredient_id: "i2", matched_name: "basilico", confident: false },
    { raw_name: "zafferano di Navelli", role: "secondary", quantity_text: "1 bustina",
      ingredient_id: null, matched_name: null, confident: false },
  ],
};

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AiDraftScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

async function proposeDraft() {
  await userEvent.type(screen.getByLabelText("Cosa vuoi cucinare"), "qualcosa di veloce");
  await userEvent.click(screen.getByRole("button", { name: "Proponi" }));
}

describe("AiDraftScreen", () => {
  it("mostra la bozza proposta dal modello", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DRAFT), { status: 200 })
    ));
    renderScreen();
    await proposeDraft();

    expect(await screen.findByDisplayValue("Pasta al pomodoro")).toBeDefined();
  });

  it("segnala gli agganci incerti, perché la conferma spetta a te", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DRAFT), { status: 200 })
    ));
    renderScreen();
    await proposeDraft();

    expect(await screen.findByText(/basilico.*da confermare/i)).toBeDefined();
  });

  it("non salva gli ingredienti senza aggancio, e lo dice", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DRAFT), { status: 200 })
    ));
    renderScreen();
    await proposeDraft();

    expect(await screen.findByText(/zafferano di Navelli.*non in anagrafica/i)).toBeDefined();
  });

  it("salva solo gli ingredienti agganciati, con provenienza AI", async () => {
    const spy = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(DRAFT), { status: 200 }))
      .mockResolvedValue(new Response(JSON.stringify({ ...DRAFT, id: "r9" }), { status: 201 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await userEvent.click(await screen.findByRole("button", { name: "Salva nel ricettario" }));

    const post = spy.mock.calls.find(([url]) => String(url).endsWith("/recipes"));
    const body = JSON.parse(post![1].body);
    expect(body.source).toBe("ai");
    expect(body.ingredients).toHaveLength(2);
  });

  it("dichiara il guasto quando il servizio AI non risponde", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "stesura AI non disponibile" }), { status: 503 })
    ));
    renderScreen();
    await proposeDraft();

    expect(await screen.findByRole("alert")).toBeDefined();
  });

  it("non perde il prompt scritto quando la stesura fallisce, così si può riprovare", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "stesura AI non disponibile" }), { status: 503 })
    ));
    renderScreen();
    await proposeDraft();
    await screen.findByRole("alert");

    expect(screen.getByLabelText("Cosa vuoi cucinare")).toHaveValue("qualcosa di veloce");
  });

  it("un aggancio incerto si può escludere prima di salvare, perché non va accettato in silenzio", async () => {
    const spy = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(DRAFT), { status: 200 }))
      .mockResolvedValue(new Response(JSON.stringify({ ...DRAFT, id: "r9" }), { status: 201 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();

    // il checkbox di inclusione del rigo incerto ("basilico fresco"): lo stacco
    // per togliere dalla bozza un aggancio di cui non ci si fida
    await userEvent.click(await screen.findByLabelText(/includi basilico fresco/i));
    await userEvent.click(screen.getByRole("button", { name: "Salva nel ricettario" }));

    const post = spy.mock.calls.find(([url]) => String(url).endsWith("/recipes"));
    const body = JSON.parse(post![1].body);
    expect(body.ingredients).toHaveLength(1);
    expect(body.ingredients[0].ingredient_id).toBe("i1");
  });

  it("un salvataggio fallito lo dice accanto al pulsante, senza perdere la bozza corretta", async () => {
    const spy = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(DRAFT), { status: 200 }))
      .mockResolvedValue(new Response(JSON.stringify({ detail: "errore" }), { status: 500 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await userEvent.click(await screen.findByRole("button", { name: "Salva nel ricettario" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/non sono riuscito a salvare/i);
    // la bozza resta in pagina, pronta per un altro tentativo
    expect(screen.getByDisplayValue("Pasta al pomodoro")).toBeDefined();
  });
});
