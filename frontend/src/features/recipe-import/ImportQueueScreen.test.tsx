import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ImportQueueScreen } from "./ImportQueueScreen";
import type { ImportTerm } from "../../domain/types";

const TERMINI: ImportTerm[] = [
  {
    id: "t1",
    display_name: "Rigatoni",
    occurrences: 12,
    suggestion: { ingredient_id: "i1", name: "pasta", certain: false },
    waiting_titles: ["Pasta alla norma", "Pasta al forno"],
    decided_by: null,
    decided_action: null,
    decided_name: null,
  },
  {
    id: "t2",
    display_name: "Acqua",
    occurrences: 7,
    suggestion: null,
    waiting_titles: ["Pane casereccio"],
    decided_by: null,
    decided_action: null,
    decided_name: null,
  },
];

const STATO_NORMALE = { fetched: 20, pending_recipes: 19, imported: 1, skipped: 0, pending_terms: 2 };

function renderScreen(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ImportQueueScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

/** Un fetch che risponde in base al percorso e al metodo: la schermata fa più
 * chiamate diverse, e il corpo di una Response si legge una volta sola. */
function stubFetch(route: (path: string, method: string) => [unknown, number]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init?.method ?? "GET");
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

type CodaOptions = {
  pending?: ImportTerm[];
  decided?: ImportTerm[];
  status?: typeof STATO_NORMALE;
  decideResult?: [unknown, number];
  askAiResult?: [unknown, number];
  undoStatus?: number;
  undoDetail?: string;
};

/** Monta la schermata su un unico finto `fetch` che copre tutte le rotte che usa
 * (la coda pendente, i decisi dall'AI, lo stato, la decisione a mano, il
 * bottone dell'AI, l'annullamento): un solo apparato per tutti i test di questo
 * file, esteso per i casi nuovi invece di raddoppiato con un secondo modo di
 * fingere le chiamate. */
function renderQueue(options: CodaOptions = {}) {
  const pending = options.pending ?? TERMINI;
  const decided = options.decided ?? [];
  const status = options.status ?? STATO_NORMALE;

  const spy = stubFetch((path, method) => {
    if (path.includes("/imports/terms/decide") && method === "POST") {
      return (
        options.askAiResult ?? [
          { applied: 0, created: 0, ignored: 0, still_pending: 0, unlocked: 0, remaining_terms: 0 },
          200,
        ]
      );
    }
    if (path.includes("/undo") && method === "POST") {
      if (options.undoStatus && options.undoStatus !== 200) {
        return [{ detail: options.undoDetail ?? "conflitto" }, options.undoStatus];
      }
      return [{ recipes_requeued: 0, ingredient_deleted: false, remaining_terms: 0 }, 200];
    }
    if (path.includes("/decision") && method === "POST") {
      return options.decideResult ?? [{ unlocked: 12, remaining_terms: 1 }, 200];
    }
    if (path.includes("decided_by=ai")) return [decided, 200];
    if (path.includes("/imports/terms")) return [pending, 200];
    if (path.includes("/imports/status")) return [status, 200];
    return [{}, 404];
  });
  renderScreen();
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("coda di revisione dell'import", () => {
  it("mostra il termine, quante ricette aspettano e qualche titolo", async () => {
    renderQueue();

    expect(await screen.findByText("Rigatoni")).toBeInTheDocument();
    expect(screen.getByText(/12 ricette in attesa/)).toBeInTheDocument();
    expect(screen.getByText(/Pasta alla norma/)).toBeInTheDocument();
  });

  it("confermare l'aggancio testuale manda la decisione e dice quante ricette ha sbloccato", async () => {
    const spy = renderQueue();

    await userEvent.click(await screen.findByRole("button", { name: /Forse «pasta»/i }));

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
    renderQueue({ decideResult: [{ unlocked: 1, remaining_terms: 1 }, 200] });

    await userEvent.click(await screen.findByRole("button", { name: /Forse «pasta»/i }));

    await waitFor(() => expect(screen.getByText("Sbloccata 1 ricetta.")).toBeInTheDocument());
    expect(screen.queryByText(/Sbloccate 1 ricette/)).not.toBeInTheDocument();
  });

  it("ignorare un termine lo manda come tale", async () => {
    const spy = renderQueue();

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

  it("i controlli di ogni scheda portano il termine nel nome accessibile", async () => {
    // la schermata rende una scheda per termine, e senza il nome dentro il nome
    // accessibile uno screen reader sente N controlli identici — lo stesso difetto
    // per "Collega a un altro ingrediente", "Crea un ingrediente nuovo", "Nome
    // dell'ingrediente", "Categoria" e la casella del secondario, su ogni scheda.
    renderQueue();

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

  it("un aggancio testuale certo resta il pulsante primario", async () => {
    // "coincidenza esatta su nome o alias" (match_name, certain: true) è un fatto,
    // non un'ipotesi: merita il pulsante primario, non quello retrocesso.
    const TERMINE_CERTO: ImportTerm[] = [
      {
        id: "t3",
        display_name: "Pinoli",
        occurrences: 3,
        suggestion: { ingredient_id: "i9", name: "pinolo", certain: true },
        waiting_titles: ["Pesto alla genovese"],
        decided_by: null,
        decided_action: null,
        decided_name: null,
      },
    ];
    renderQueue({
      pending: TERMINE_CERTO,
      status: { fetched: 3, pending_recipes: 3, imported: 0, skipped: 0, pending_terms: 1 },
    });

    const pulsante = await screen.findByRole("button", { name: /^Collega a pinolo$/i });
    expect(pulsante.className).toContain("bg-brand");
    expect(screen.queryByRole("button", { name: /Forse «pinolo»/i })).not.toBeInTheDocument();
  });

  // "1 ricette scaricate aspettano, 1 sono già dentro" era il testo con
  // entrambi i conteggi a 1: ogni conteggio governa la propria frase (nome,
  // verbo e participio), e qui concordano al singolare entrambi insieme.
  it("la riga di stato è al singolare quando entrambi i conteggi sono 1", async () => {
    renderQueue({
      pending: [],
      status: { fetched: 2, pending_recipes: 1, imported: 1, skipped: 0, pending_terms: 0 },
    });

    expect(
      await screen.findByText("1 ricetta scaricata aspetta, 1 è già dentro.")
    ).toBeInTheDocument();
  });

  // Il caso che una frase condivisa tra i due conteggi sbaglierebbe: uno dei
  // due è 1 e l'altro no, quindi un solo ramo non può concordare entrambi.
  it("la riga di stato tratta i due conteggi indipendentemente quando solo uno è 1", async () => {
    renderQueue({
      pending: [],
      status: { fetched: 6, pending_recipes: 1, imported: 5, skipped: 0, pending_terms: 0 },
    });

    expect(
      await screen.findByText("1 ricetta scaricata aspetta, 5 sono già dentro.")
    ).toBeInTheDocument();
  });

  it("a coda vuota dice che non c'è niente da fare", async () => {
    renderQueue({
      pending: [],
      status: { fetched: 20, pending_recipes: 0, imported: 20, skipped: 0, pending_terms: 0 },
    });

    expect(await screen.findByText(/Niente da abbinare/i)).toBeInTheDocument();
  });

  it("un 409 sulla decisione mostra il motivo del backend, non la frase generica", async () => {
    // Il caso che conta: "Sale fino" rinominato nel generico "sale" mentre un
    // ingrediente "sale" esiste già. Il backend risponde 409 con un `detail`
    // che dice la via d'uscita (collegare invece di creare); la frase generica
    // "riprova" nasconderebbe esattamente quella via.
    renderQueue({
      decideResult: [
        { detail: "«sale» è già in anagrafica: collega il termine invece di creare un doppione." },
        409,
      ],
    });

    await userEvent.click(await screen.findByRole("button", { name: /Forse «pasta»/i }));

    expect(
      await screen.findByText(/«sale» è già in anagrafica: collega il termine/)
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Non sono riuscito a registrare la decisione/)
    ).not.toBeInTheDocument();
  });

  it("un 500 sulla decisione resta sulla frase generica, con la rassicurazione", async () => {
    renderQueue({ decideResult: [{ detail: "rotto" }, 500] });

    await userEvent.click(await screen.findByRole("button", { name: /Forse «pasta»/i }));

    expect(
      await screen.findByText(/Non sono riuscito a registrare la decisione\. Niente è andato perso: riprova\./)
    ).toBeInTheDocument();
  });

  it("se la coda non risponde lo dice insieme a cosa resta possibile", async () => {
    stubFetch((path) => {
      if (path.includes("/imports/terms")) return [{ detail: "rotto" }, 500];
      return [{}, 500];
    });
    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent(/ricettario/i);
  });

  it("mostra l'elenco di quel che l'AI ha deciso, con il suo annulla", async () => {
    // il finto di questo file serve già /imports/terms: aggiungi la risposta per
    // ?decided_by=ai usando lo stesso apparato, non un secondo modo di fingere
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta",
        },
      ],
    });
    expect(await screen.findByText("Rigatoni")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    ).toBeInTheDocument();
  });

  it("un 409 sull'annullamento chiede conferma invece di fallire", async () => {
    // è l'unico punto della feature in cui si chiede qualcosa: se questo test non
    // c'è, la perdita del collegamento allo storico diventa invisibile
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta",
        },
      ],
      undoStatus: 409,
      undoDetail: "1 di queste ricette le hai già cucinate: conferma per procedere.",
    });
    await userEvent.click(
      await screen.findByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    );
    expect(await screen.findByText(/già cucinate/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /rifai comunque/i })).toBeInTheDocument();
  });

  it("confermare l'annullamento dopo il 409 lo rimanda con `force`", async () => {
    // senza `force` il secondo tentativo tornerebbe di nuovo 409, e "Rifai
    // comunque" sarebbe un pulsante che non fa mai quel che dice
    const decisi: ImportTerm[] = [
      {
        id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
        waiting_titles: [], decided_by: "ai", decided_action: "map",
        decided_name: "pasta",
      },
    ];
    let chiamateUndo = 0;
    stubFetch((path, method) => {
      if (path.includes("/undo") && method === "POST") {
        chiamateUndo += 1;
        if (chiamateUndo === 1) {
          return [{ detail: "1 di queste ricette le hai già cucinate." }, 409];
        }
        return [{ recipes_requeued: 1, ingredient_deleted: false, remaining_terms: 0 }, 200];
      }
      if (path.includes("decided_by=ai")) return [decisi, 200];
      if (path.includes("/imports/terms")) return [[], 200];
      if (path.includes("/imports/status")) return [STATO_NORMALE, 200];
      return [{}, 404];
    });
    renderScreen();

    await userEvent.click(
      await screen.findByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    );
    await screen.findByText(/già cucinate/i);

    const rifaiComunque = screen.getByRole("button", { name: /rifai comunque/i });
    await userEvent.click(rifaiComunque);

    await waitFor(() => expect(chiamateUndo).toBe(2));
  });

  it("chiedere all'AI applica la coda e dice cosa ha sbloccato", async () => {
    const spy = renderQueue({
      askAiResult: [
        { applied: 2, created: 0, ignored: 1, still_pending: 0, unlocked: 5, remaining_terms: 0 },
        200,
      ],
    });

    await userEvent.click(await screen.findByRole("button", { name: /Riprova con l'AI/i }));

    await waitFor(() => expect(screen.getByText(/Sbloccate 5 ricette/)).toBeInTheDocument());
    const chiamata = spy.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/imports/terms/decide") &&
        (init as RequestInit | undefined)?.method === "POST"
    );
    expect(JSON.parse(String((chiamata?.[1] as RequestInit).body))).toEqual({});
  });

  it("un 503 dell'AI lo dice col messaggio del backend, e la coda resta usabile a mano", async () => {
    // Mai un vicolo cieco: il modello irraggiungibile non deve impedire di
    // decidere a mano. Il messaggio specifico del 503 (non quello generico)
    // è l'unica prova che il branch sullo status è ancora lì.
    renderQueue({
      askAiResult: [{ detail: "il modello non risponde: decidi a mano." }, 503],
    });

    await userEvent.click(await screen.findByRole("button", { name: /Riprova con l'AI/i }));

    expect(await screen.findByText(/il modello non risponde: decidi a mano\./i)).toBeInTheDocument();
    expect(
      screen.queryByText(/Non sono riuscito a chiedere all'AI/i)
    ).not.toBeInTheDocument();
    // i controlli a mano restano lì, invariati dal fallimento dell'AI
    expect(screen.getByRole("button", { name: /Forse «pasta»/i })).toBeEnabled();
  });
});
