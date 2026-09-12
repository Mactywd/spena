import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import { ImportQueueScreen } from "./ImportQueueScreen";

const TERMINI = [
  {
    id: "t1",
    display_name: "Rigatoni",
    occurrences: 12,
    suggestion: { ingredient_id: "i1", name: "pasta", certain: false },
    waiting_titles: ["Pasta alla norma", "Pasta al forno"],
  },
  {
    id: "t2",
    display_name: "Acqua",
    occurrences: 7,
    suggestion: null,
    waiting_titles: ["Pane casereccio"],
  },
];

const PROPOSTE = {
  proposals: [
    { term_id: "t1", action: "map", ingredient_id: "i1", name: null,
      display_name: null, category: null },
    { term_id: "t2", action: "ignore", ingredient_id: null, name: null,
      display_name: null, category: null },
  ],
};

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ImportQueueScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

/** Un fetch che risponde in base al percorso e al metodo: la schermata fa tre
 * chiamate diverse, e il corpo di una Response si legge una volta sola. */
function stubFetch(route: (path: string, method: string) => [unknown, number]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init?.method ?? "GET");
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

const CODA_NORMALE = (path: string, method: string): [unknown, number] => {
  if (path.includes("/imports/terms/proposals")) return [PROPOSTE, 200];
  if (path.includes("/imports/terms") && method === "POST")
    return [{ unlocked: 12, remaining_terms: 1 }, 200];
  if (path.includes("/imports/terms")) return [TERMINI, 200];
  if (path.includes("/imports/status"))
    return [
      { fetched: 20, pending_recipes: 19, imported: 1, skipped: 0, pending_terms: 2 },
      200,
    ];
  return [{}, 404];
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("coda di revisione dell'import", () => {
  it("mostra il termine, quante ricette aspettano e qualche titolo", async () => {
    stubFetch(CODA_NORMALE);
    renderScreen();

    expect(await screen.findByText("Rigatoni")).toBeInTheDocument();
    expect(screen.getByText(/12 ricette in attesa/)).toBeInTheDocument();
    expect(screen.getByText(/Pasta alla norma/)).toBeInTheDocument();
  });

  it("la proposta di Claude diventa un pulsante che dice cosa farà", async () => {
    stubFetch(CODA_NORMALE);
    renderScreen();

    expect(
      await screen.findByRole("button", { name: /Collega a pasta/i })
    ).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /^Ignora «Acqua»$/ })).toBeInTheDocument();
  });

  it("il pulsante mostra il nome della proposta anche quando differisce dal suggerimento testuale", async () => {
    // il caso che la revisione esiste per coprire: Claude sceglie un ingrediente
    // diverso da quello trovato per somiglianza del nome ("pasta" per "Rigatoni").
    // Senza il nome portato dalla proposta, il pulsante cadrebbe sul generico
    // "Collega a l'ingrediente" — chiedendo di confermare qualcosa che non si vede.
    stubFetch((path, method) => {
      if (path.includes("/imports/terms/proposals"))
        return [
          {
            proposals: [
              { term_id: "t1", action: "map", ingredient_id: "i2", name: "sugo di pomodoro",
                display_name: null, category: null },
              { term_id: "t2", action: "ignore", ingredient_id: null, name: null,
                display_name: null, category: null },
            ],
          },
          200,
        ];
      if (path.includes("/imports/terms") && method === "POST")
        return [{ unlocked: 12, remaining_terms: 1 }, 200];
      if (path.includes("/imports/terms")) return [TERMINI, 200];
      if (path.includes("/imports/status"))
        return [
          { fetched: 20, pending_recipes: 19, imported: 1, skipped: 0, pending_terms: 2 },
          200,
        ];
      return [{}, 404];
    });
    renderScreen();

    expect(
      await screen.findByRole("button", { name: /Collega a sugo di pomodoro/i })
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Collega a pasta/i })).not.toBeInTheDocument();
  });

  it("confermare la proposta manda la decisione e dice quante ricette ha sbloccato", async () => {
    const spy = stubFetch(CODA_NORMALE);
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: /Collega a pasta/i }));

    await waitFor(() => expect(screen.getByText(/Sbloccate 12 ricette/)).toBeInTheDocument());
    const decisione = spy.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/imports/terms/t1/decision") &&
        (init as RequestInit | undefined)?.method === "POST"
    );
    expect(JSON.parse(String((decisione?.[1] as RequestInit).body))).toEqual({
      action: "map",
      ingredient_id: "i1",
    });
  });

  // "Sbloccate 1 ricette." era il testo con una sola ricetta sbloccata: il
  // plurale sbagliato in numero e genere, lo stesso difetto che TermCard.tsx
  // già tratta correttamente.
  it("sbloccare una sola ricetta lo dice al singolare", async () => {
    stubFetch((path, method) => {
      if (path.includes("/imports/terms/proposals")) return [PROPOSTE, 200];
      if (path.includes("/imports/terms") && method === "POST")
        return [{ unlocked: 1, remaining_terms: 1 }, 200];
      if (path.includes("/imports/terms")) return [TERMINI, 200];
      if (path.includes("/imports/status"))
        return [
          { fetched: 20, pending_recipes: 19, imported: 1, skipped: 0, pending_terms: 2 },
          200,
        ];
      return [{}, 404];
    });
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: /Collega a pasta/i }));

    await waitFor(() => expect(screen.getByText("Sbloccata 1 ricetta.")).toBeInTheDocument());
    expect(screen.queryByText(/Sbloccate 1 ricette/)).not.toBeInTheDocument();
  });

  it("ignorare un termine lo manda come tale", async () => {
    const spy = stubFetch(CODA_NORMALE);
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: /^Ignora «Acqua»$/ }));

    await waitFor(() => {
      const inviata = spy.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/imports/terms/t2/decision") &&
          (init as RequestInit | undefined)?.method === "POST"
      );
      expect(JSON.parse(String((inviata?.[1] as RequestInit).body))).toEqual({
        action: "ignore",
      });
    });
  });

  it("una decisione non svuota la coda, e non richiede di nuovo le proposte già note", async () => {
    // Uno stub che si comporta come il backend vero: dopo la decisione, l'elenco
    // dei termini in attesa si accorcia da sé (il backend filtra ai soli pendenti).
    // Uno stub statico non può vedere né il blank-out né la richiesta ripetuta: è
    // esattamente perché non lo vedeva che il difetto critico è passato i test.
    let decisa = false;
    const spy = stubFetch((path, method) => {
      if (path.includes("/imports/terms/proposals")) return [PROPOSTE, 200];
      if (path.includes("/imports/terms") && method === "POST") {
        decisa = true;
        return [{ unlocked: 12, remaining_terms: 1 }, 200];
      }
      if (path.includes("/imports/terms")) return [decisa ? [TERMINI[1]] : TERMINI, 200];
      if (path.includes("/imports/status"))
        return [
          { fetched: 20, pending_recipes: 19, imported: 1, skipped: 0, pending_terms: 2 },
          200,
        ];
      return [{}, 404];
    });
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: /Collega a pasta/i }));

    // subito dopo il tocco, prima ancora che la decisione torni: la coda non deve
    // sparire dietro un nuovo "Carico la coda…"
    expect(screen.queryByText(/Carico la coda/i)).not.toBeInTheDocument();

    await waitFor(() => expect(screen.getByText(/Sbloccate 12 ricette/)).toBeInTheDocument());

    // "Acqua" resta in vista: l'elenco più corto che torna dal backend non ha mai
    // fatto sparire la scheda dietro uno spinner
    expect(await screen.findByText("Acqua")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /^Ignora «Acqua»$/ })).toBeInTheDocument();

    const chiamateProposte = spy.mock.calls.filter(([url]) =>
      String(url).includes("/imports/terms/proposals")
    );
    expect(chiamateProposte).toHaveLength(1);
  });

  it("i controlli di ogni scheda portano il termine nel nome accessibile", async () => {
    // la schermata rende una scheda per termine, e senza il nome dentro il nome
    // accessibile uno screen reader sente N controlli identici — lo stesso difetto
    // per "Collega a un altro ingrediente", "Crea un ingrediente nuovo", "Nome
    // dell'ingrediente", "Categoria" e la casella del secondario, su ogni scheda.
    stubFetch(CODA_NORMALE);
    renderScreen();

    await screen.findByText("Rigatoni");

    expect(
      screen.getByRole("textbox", { name: /Collega «Rigatoni» a un altro ingrediente/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: /Collega «Acqua» a un altro ingrediente/i })
    ).toBeInTheDocument();

    const creaRigatoni = screen.getByRole("button", {
      name: /Crea un ingrediente nuovo per «Rigatoni»/i,
    });
    expect(creaRigatoni).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Crea un ingrediente nuovo per «Acqua»/i })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("checkbox", {
        name: /Di solito «Rigatoni» è un ingrediente secondario/i,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: /Di solito «Acqua» è un ingrediente secondario/i })
    ).toBeInTheDocument();

    // apre il modulo di creazione sulla scheda di "Rigatoni": gli stessi controlli
    // sull'altra scheda avrebbero lo stesso nome visibile ("Nome dell'ingrediente",
    // "Categoria") se il nome accessibile non portasse anche lui il termine
    await userEvent.click(creaRigatoni);

    expect(
      screen.getByRole("textbox", { name: /Nome dell'ingrediente per «Rigatoni»/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: /Categoria per «Rigatoni»/i })
    ).toBeInTheDocument();
  });

  it("senza le proposte la coda funziona e lo dichiara", async () => {
    stubFetch((path, method) => {
      if (path.includes("/imports/terms/proposals")) return [{ detail: "no" }, 503];
      return CODA_NORMALE(path, method);
    });
    renderScreen();

    // l'elenco compare appena arrivano i termini, senza aspettare le proposte (è
    // il punto del difetto critico corretto qui): "decidi a mano" arriva un giro
    // dopo, quando il tentativo di Claude si è dichiarato fallito, non nello stesso
    // render di "Rigatoni" — per questo è un `findByText`, non un `getByText`.
    expect(await screen.findByText("Rigatoni")).toBeInTheDocument();
    expect(await screen.findByText(/decidi a mano/i)).toBeInTheDocument();

    // "Rigatoni" ha solo il suggerimento testuale (`certain: false`, una
    // somiglianza trigram con "pasta", non una proposta di Claude che qui non è
    // mai arrivata): resta una via in un tocco, ma retrocessa, non il pulsante
    // primario "Collega a pasta" che il difetto critico rendeva. Quella frase
    // asserirebbe un aggancio che nessuno ha verificato — esattamente come
    // "Collega a pisello" per "Pinoli".
    const scorciatoia = await screen.findByRole("button", { name: /Forse «pasta»/i });
    expect(scorciatoia).toBeInTheDocument();
    expect(scorciatoia.className).not.toContain("bg-brand");
    expect(screen.queryByRole("button", { name: /^Collega a pasta$/i })).not.toBeInTheDocument();
  });

  it("un aggancio testuale certo resta un tocco solo anche senza proposta di Claude", async () => {
    // "coincidenza esatta su nome o alias" (match_name, certain: true) è un fatto,
    // non un'ipotesi: merita lo stesso pulsante primario di una proposta di
    // Claude, anche quando Claude non ha proposto niente per questo termine.
    const TERMINE_CERTO = [
      {
        id: "t3",
        display_name: "Pinoli",
        occurrences: 3,
        suggestion: { ingredient_id: "i9", name: "pinolo", certain: true },
        waiting_titles: ["Pesto alla genovese"],
      },
    ];
    stubFetch((path) => {
      if (path.includes("/imports/terms/proposals")) return [{ proposals: [] }, 200];
      if (path.includes("/imports/terms")) return [TERMINE_CERTO, 200];
      if (path.includes("/imports/status"))
        return [
          { fetched: 3, pending_recipes: 3, imported: 0, skipped: 0, pending_terms: 1 },
          200,
        ];
      return [{}, 404];
    });
    renderScreen();

    const pulsante = await screen.findByRole("button", { name: /^Collega a pinolo$/i });
    expect(pulsante.className).toContain("bg-brand");
    expect(screen.queryByRole("button", { name: /Forse «pinolo»/i })).not.toBeInTheDocument();
  });

  // "1 ricette scaricate aspettano, 1 sono già dentro" era il testo con
  // entrambi i conteggi a 1: ogni conteggio governa la propria frase (nome,
  // verbo e participio), e qui concordano al singolare entrambi insieme.
  it("la riga di stato è al singolare quando entrambi i conteggi sono 1", async () => {
    stubFetch((path) => {
      if (path.includes("/imports/terms/proposals")) return [{ proposals: [] }, 200];
      if (path.includes("/imports/terms")) return [[], 200];
      if (path.includes("/imports/status"))
        return [
          { fetched: 2, pending_recipes: 1, imported: 1, skipped: 0, pending_terms: 0 },
          200,
        ];
      return [{}, 404];
    });
    renderScreen();

    expect(
      await screen.findByText("1 ricetta scaricata aspetta, 1 è già dentro.")
    ).toBeInTheDocument();
  });

  // Il caso che una frase condivisa tra i due conteggi sbaglierebbe: uno dei
  // due è 1 e l'altro no, quindi un solo ramo non può concordare entrambi.
  it("la riga di stato tratta i due conteggi indipendentemente quando solo uno è 1", async () => {
    stubFetch((path) => {
      if (path.includes("/imports/terms/proposals")) return [{ proposals: [] }, 200];
      if (path.includes("/imports/terms")) return [[], 200];
      if (path.includes("/imports/status"))
        return [
          { fetched: 6, pending_recipes: 1, imported: 5, skipped: 0, pending_terms: 0 },
          200,
        ];
      return [{}, 404];
    });
    renderScreen();

    expect(
      await screen.findByText("1 ricetta scaricata aspetta, 5 sono già dentro.")
    ).toBeInTheDocument();
  });

  it("a coda vuota dice che non c'è niente da fare", async () => {
    stubFetch((path) => {
      if (path.includes("/imports/terms/proposals")) return [{ proposals: [] }, 200];
      if (path.includes("/imports/terms")) return [[], 200];
      return [
        { fetched: 20, pending_recipes: 0, imported: 20, skipped: 0, pending_terms: 0 },
        200,
      ];
    });
    renderScreen();

    expect(await screen.findByText(/Niente da abbinare/i)).toBeInTheDocument();
  });

  it("un 503 permanente delle proposte non viene ritentato", async () => {
    // `renderScreen()` qui sopra usa un client con `retry: false` globale, che
    // nasconderebbe proprio il difetto che questo test copre (una query che
    // prova a ritentare perché non ha il suo `retry: false`): il client qui
    // usa il default vero di App.tsx (retry finché count < 2, salvo 401), per
    // esercitare la stessa forma del problema. Il 503 di questa rotta quando
    // manca ANTHROPIC_API_KEY è un degrado dichiarato e permanente per tutta
    // la vita del processo, non un intoppo passeggero: senza `retry: false`
    // sulla query delle proposte, un client con questo default la ritenterebbe
    // due volte in più, per tre giri di rete a vuoto prima che compaia "decidi
    // a mano".
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          retry: defaultQueryRetryPredicate,
        },
      },
    });
    const spy = stubFetch((path, method) => {
      if (path.includes("/imports/terms/proposals")) return [{ detail: "manca la chiave" }, 503];
      return CODA_NORMALE(path, method);
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ImportQueueScreen />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await screen.findByText(/decidi a mano/i);

    const chiamateProposte = spy.mock.calls.filter(([url]) =>
      String(url).includes("/imports/terms/proposals")
    );
    expect(chiamateProposte).toHaveLength(1);
  });

  it("se la coda non risponde lo dice insieme a cosa resta possibile", async () => {
    stubFetch((path) => {
      if (path.includes("/imports/terms")) return [{ detail: "rotto" }, 500];
      return [{}, 500];
    });
    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent(/ricettario/i);
  });
});
