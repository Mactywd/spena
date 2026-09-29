import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";

const ITEMS = [
  { id: "s1", raw_text: "pomodoro", ingredient_id: "i1", ingredient_name: "pomodoro",
    ingredient_category: "verdura", status: "pending", reason: "manual",
    created_at: "2026-09-11T10:00:00Z" },
];

describe("App", () => {
  it("riporta alla schermata di accesso quando una mutazione riceve un 401", async () => {
    // la lista carica normalmente, ma spuntare una voce (una mutazione, non una query)
    // trova la sessione scaduta: anche la MutationCache deve riportare al login.
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return Promise.resolve(new Response("", { status: 401 }));
      }
      return Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const checkbox = await screen.findByRole("checkbox", { name: /pomodoro/ });
    await userEvent.click(checkbox);

    expect(await screen.findByRole("button", { name: "Entra" })).toBeDefined();
  });

  it(
    "un errore che non è un 401 non viene ritentato all'infinito: lo schermo lo dice",
    async () => {
      // Questa prova gira sul QueryClient vero dell'app, non su uno costruito con
      // retry:false dentro al test: è l'unico modo di accorgersi che il predicato
      // di retry ignora il conteggio e ritenta per sempre. Con quel difetto
      // `isError` non diventa mai vero e OGNI ramo d'errore dell'app — lista,
      // dispensa, ricettario, dettaglio ricetta — è morto in produzione, mentre
      // i test di quei rami passano tutti col loro client locale.
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));
      window.history.pushState({}, "", "/lista");

      render(<App />);

      // i tentativi hanno un'attesa crescente (1s, 2s): il limite è che finiscano,
      // non quanto durino
      expect(await screen.findByRole("alert", {}, { timeout: 10_000 })).toHaveTextContent(
        /non sono riuscito a caricare la lista/i
      );
    },
    20_000
  );

  it("l'intestazione sta sopra le schermate, non dentro una di loro", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(ITEMS), { status: 200 })
    ));

    render(<App />);

    expect(await screen.findByRole("banner")).toBeDefined();
    expect(screen.getByRole("link", { name: "Spena" })).toBeDefined();
  });

  it("un indirizzo che non esiste dice «Pagina non trovata» e porta alla lista", async () => {
    window.history.pushState({}, "", "/non-esiste");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Pagina non trovata" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Torna alla lista" })).toHaveAttribute("href", "/lista");
  });

  it("una ricetta che non c'è più lo dice subito, senza ritentare, e riporta al ricettario", async () => {
    // Sul QueryClient vero dell'app, come la prova sul 500 qui sopra: gli schermi si
    // provano con `retry: false`, e un 404 ritentato non lo vedrebbero mai. Qui sì: con
    // i ritentativi il messaggio arriverebbe dopo le attese di 1 s e 2 s, fuori dal
    // secondo che `findBy` aspetta
    const fetchMock = vi.fn((url: string) =>
      Promise.resolve(
        String(url).includes("/recipes/r-sparita")
          ? new Response(JSON.stringify({ detail: "ricetta inesistente" }), { status: 404 })
          : new Response("[]", { status: 200 })
      )
    );
    vi.stubGlobal("fetch", fetchMock);
    window.history.pushState({}, "", "/ricette/r-sparita");

    render(<App />);

    expect(await screen.findByText("Questa ricetta non c'è più.")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/recipes/r-sparita"))
    ).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Torna al ricettario" })).toHaveAttribute("href", "/ricette");
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
  });
});
