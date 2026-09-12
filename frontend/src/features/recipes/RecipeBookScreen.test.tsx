import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RecipeBookScreen } from "./RecipeBookScreen";

const RESULTS = [
  { id: "r1", title: "Pasta all'aglio", description: "Svelta", source: "dataset",
    missing: 0, cookable: true },
  { id: "r2", title: "Pasta al pomodoro", description: "Di sempre", source: "ai",
    missing: 1, cookable: false },
];

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RecipeBookScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RecipeBookScreen", () => {
  it("mostra la provenienza di ogni ricetta", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(RESULTS), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("dataset")).toBeDefined();
    expect(screen.getByText("AI")).toBeDefined();
  });

  it("dice quanto manca, senza nascondere la ricetta", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(RESULTS), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("Pasta al pomodoro")).toBeDefined();
    expect(screen.getByText("manca 1 ingrediente")).toBeDefined();
  });

  it("segnala le ricette che puoi cucinare adesso", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(RESULTS), { status: 200 })
    ));
    renderScreen();
    expect(await screen.findByText("Puoi cucinarla ora")).toBeDefined();
  });

  it("la ricerca passa la query al backend", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(JSON.stringify(RESULTS), { status: 200 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.type(await screen.findByLabelText("Cerca nel ricettario"), "pomodoro");

    await vi.waitFor(() =>
      expect(spy.mock.calls.some(([url]) => String(url).includes("q=pomodoro"))).toBe(true)
    );
  });

  it("il filtro restringe alle sole ricette cucinabili", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(JSON.stringify(RESULTS), { status: 200 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.click(await screen.findByLabelText("Solo quelle che posso cucinare"));

    await vi.waitFor(() =>
      expect(spy.mock.calls.some(([url]) => String(url).includes("only_cookable=true"))).toBe(true)
    );
  });

  // Pattern 2 delle istruzioni: una ricerca fallita deve dirlo, non sembrare un
  // ricettario vuoto. Una ricerca semantica senza risultati ha esattamente lo
  // stesso aspetto di una ricerca rotta, quindi qui la distinzione conta di più.
  it("una ricerca fallita lo dice, e non sembra un ricettario vuoto", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    renderScreen();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/non sono riuscito/i);
    expect(screen.queryByText(/nessuna ricetta/i)).toBeNull();

    // il campo di ricerca resta utilizzabile: mai un vicolo cieco
    expect(screen.getByLabelText("Cerca nel ricettario")).not.toBeDisabled();
  });

  // Pattern 3: una risposta lenta e superata non deve sovrascrivere una risposta
  // più recente e già arrivata. Stesso tipo di guardia costata un MAJOR nel
  // Task 18 per AddItemField, qui sulla ricerca del ricettario. La ricerca
  // sul montaggio (query vuota) deve risolversi per conto suo, quindi le due
  // ricerche in gara si distinguono dall'URL, non dall'ordine di chiamata.
  it("una risposta lenta e superata non sovrascrive quella più recente", async () => {
    let releaseSlow: (response: Response) => void = () => {};
    let releaseFast: (response: Response) => void = () => {};
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.includes("q=pollo")) {
        return new Promise<Response>((resolve) => { releaseSlow = resolve; });
      }
      if (href.includes("q=pesce")) {
        return new Promise<Response>((resolve) => { releaseFast = resolve; });
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderScreen();
    const field = await screen.findByLabelText("Cerca nel ricettario");

    await userEvent.type(field, "pollo");
    await vi.waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes("q=pollo"))).toBe(true)
    );

    await userEvent.clear(field);
    await userEvent.type(field, "pesce");
    await vi.waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes("q=pesce"))).toBe(true)
    );

    // la rapida arriva prima...
    releaseFast(new Response(JSON.stringify([
      { id: "rf", title: "Risotto al pesce", description: null, source: "dataset",
        missing: 0, cookable: true },
    ]), { status: 200 }));
    expect(await screen.findByText("Risotto al pesce")).toBeDefined();

    // ...e quella lenta, superata, arriva dopo: non deve cambiare nulla
    releaseSlow(new Response(JSON.stringify([
      { id: "rs", title: "Pollo al forno", description: null, source: "dataset",
        missing: 0, cookable: true },
    ]), { status: 200 }));
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(screen.getByText("Risotto al pesce")).toBeDefined();
    expect(screen.queryByText("Pollo al forno")).toBeNull();
  });
});
