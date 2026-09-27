import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ImportQueueScreen } from "./ImportQueueScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
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
    decided_at: null,
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
    decided_at: null,
  },
];

const STATO_NORMALE = { fetched: 20, pending_recipes: 19, imported: 1, skipped: 0, pending_terms: 2 };

// Il predicato vero di App.tsx, non un `retry: false` di comodo: CLAUDE.md lo dice
// verbatim (primo punto) — un client che si costruisce da sé non prova niente sul
// client vero. Con successi ovunque (il caso della quasi totalità dei test di
// questo file) non cambia niente: il predicato conta solo quando una query fallisce
// per davvero, ed è lì che deve essere questo e non un altro.
function renderScreen(
  client = new QueryClient({ defaultOptions: { queries: { retry: defaultQueryRetryPredicate } } }),
  path = "/ricette/importa"
) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
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
  humanDecided?: ImportTerm[];
  status?: typeof STATO_NORMALE;
  decideResult?: [unknown, number];
  askAiResult?: [unknown, number];
  undoStatus?: number;
  undoDetail?: string;
  /** `ingredient_deleted` di un annullamento riuscito */
  undoDeleted?: boolean;
  /** l'indirizzo della schermata, per `?termine=` */
  path?: string;
  /** la risposta di `GET /imports/terms/{id}`, il termine messo a fuoco */
  focused?: [unknown, number];
  /** il client della schermata; senza, quello col predicato di retry vero */
  client?: QueryClient;
};

/** Monta la schermata su un unico finto `fetch` che copre tutte le rotte che usa
 * (la coda pendente, i decisi dall'AI, lo stato, la decisione a mano, il
 * bottone dell'AI, l'annullamento): un solo apparato per tutti i test di questo
 * file, esteso per i casi nuovi invece di raddoppiato con un secondo modo di
 * fingere le chiamate. */
function renderQueue(options: CodaOptions = {}) {
  const pending = options.pending ?? TERMINI;
  const decided = options.decided ?? [];
  const humanDecided = options.humanDecided ?? [];
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
      return [
        { recipes_requeued: 0, ingredient_deleted: options.undoDeleted ?? false, remaining_terms: 0 },
        200,
      ];
    }
    if (path.includes("/decision") && method === "POST") {
      return options.decideResult ?? [{ unlocked: 12, remaining_terms: 1 }, 200];
    }
    if (/\/imports\/terms\/[^/?]+$/.test(path) && method === "GET") {
      return options.focused ?? [{ detail: "termine inesistente" }, 404];
    }
    if (path.includes("decided_by=ai")) return [decided, 200];
    if (path.includes("decided_by=human")) return [humanDecided, 200];
    if (path.includes("/imports/terms")) return [pending, 200];
    if (path.includes("/imports/status")) return [status, 200];
    return [{}, 404];
  });
  renderScreen(options.client, options.path);
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
        decided_at: null,
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

  it(
    "se la coda non risponde lo dice insieme a cosa resta possibile",
    async () => {
      stubFetch((path) => {
        if (path.includes("/imports/terms")) return [{ detail: "rotto" }, 500];
        return [{}, 500];
      });
      renderScreen();

      // Con il predicato vero (sopra) un 500 permanente si vede solo dopo i due
      // tentativi che quel predicato concede, non al primo giro: il timeout più
      // lungo copre quell'attesa reale, non la nasconde.
      expect(await screen.findByRole("alert", {}, { timeout: 8000 })).toHaveTextContent(
        /ricettario/i
      );
    },
    10000
  );

  it("mostra l'elenco di quel che l'AI ha deciso, con il suo annulla", async () => {
    // il finto di questo file serve già /imports/terms: aggiungi la risposta per
    // ?decided_by=ai usando lo stesso apparato, non un secondo modo di fingere
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta", decided_at: "2026-09-20T10:00:00Z",
        },
      ],
    });
    expect(await screen.findByText("Rigatoni")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    ).toBeInTheDocument();
  });

  it("un 409 sull'annullamento è un rifiuto detto col suo motivo, non una domanda", async () => {
    // Dalla S9 il backend non chiede più conferma per le ricette già cucinate: le
    // cotture si ri-legano alla ricetta rifatta. L'unico 409 che resta è il termine
    // già in coda, e lì non c'è niente da confermare.
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta", decided_at: "2026-09-20T10:00:00Z",
        },
      ],
      undoStatus: 409,
      undoDetail: "«Rigatoni» è già in coda: non c'è nessuna decisione da disfare.",
    });

    await userEvent.click(
      await screen.findByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    );

    expect(
      await screen.findByText(/«Rigatoni» è già in coda: non c'è nessuna decisione da disfare\./)
    ).toBeInTheDocument();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /rifai comunque/i })).not.toBeInTheDocument();
  });

  it("l'annullamento non manda più `force`", async () => {
    const spy = renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta", decided_at: "2026-09-20T10:00:00Z",
        },
      ],
      undoStatus: 200,
    });

    await userEvent.click(
      await screen.findByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    );

    await waitFor(() => {
      const undo = spy.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/undo") && (init as RequestInit | undefined)?.method === "POST"
      );
      expect(undo).toBeDefined();
      expect((undo![1] as RequestInit).body).toBeUndefined();
    });
  });

  it("un 500 sull'annullamento si vede, invece di sembrare un tocco ignorato", async () => {
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta", decided_at: "2026-09-20T10:00:00Z",
        },
      ],
      undoStatus: 500,
      undoDetail: "rotto",
    });

    await userEvent.click(
      await screen.findByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    );

    expect(
      await screen.findByText(
        /Non sono riuscito ad annullare la decisione\. Niente è andato perso: riprova\./
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("un annullamento riuscito dice quante ricette sono tornate in coda", async () => {
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta", decided_at: "2026-09-20T10:00:00Z",
        },
      ],
      undoStatus: 200,
    });

    await userEvent.click(
      await screen.findByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    );

    // `UndoOut` porta `recipes_requeued` e `ingredient_deleted`: la revisione
    // dell'annullamento (l'unica conferma distruttiva della feature) non dice
    // cosa ha distrutto se questi due numeri restano non mostrati.
    expect(
      await screen.findByText("Nessuna ricetta è tornata in coda.")
    ).toBeInTheDocument();
  });

  it("un annullamento che ha cancellato l'ingrediente creato lo dice, e solo allora", async () => {
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Speck", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "speck", decided_at: "2026-09-20T10:00:00Z",
        },
      ],
      undoStatus: 200,
      undoDeleted: true,
    });

    await userEvent.click(
      await screen.findByRole("button", { name: /annulla la decisione su «Speck»/i })
    );

    expect(
      await screen.findByText(/L'ingrediente che questa decisione aveva creato è stato eliminato/)
    ).toBeInTheDocument();
  });

  it("l'elenco delle decisioni recenti dice quando annullare cancella l'ingrediente e quando no", async () => {
    // Il backend cancella solo un ingrediente che la decisione ha scritto di aver
    // creato (`created_ingredient`), e che niente altro usa: un aggancio a uno che
    // c'era già («pasta» sotto «Rigatoni») e le decisioni di prima lo lasciano.
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta", decided_at: "2026-09-20T10:00:00Z",
        },
      ],
    });

    await screen.findByText("Rigatoni");
    expect(
      screen.getByText(/se questa decisione l'aveva creato e niente altro lo usa, l'annullamento lo cancella/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/altrimenti resta in anagrafica/i)).toBeInTheDocument();
  });

  describe("decisioni recenti (R11): quelle a mano accanto a quelle dell'AI", () => {
    function deciso(overrides: Partial<ImportTerm>): ImportTerm {
      return {
        id: "t0", display_name: "?", occurrences: 1, suggestion: null,
        waiting_titles: [], decided_by: "ai", decided_action: "map",
        decided_name: "pasta", decided_at: "2026-09-20T10:00:00Z",
        ...overrides,
      };
    }

    it("chiede anche le decisioni prese a mano, con lo stesso tetto di quelle dell'AI", async () => {
      const spy = renderQueue({ pending: [] });
      await waitFor(() =>
        expect(
          spy.mock.calls.some(([url]) =>
            String(url).includes("/imports/terms?decided_by=human&limit=50")
          )
        ).toBe(true)
      );
    });

    it("una decisione presa a mano compare nell'elenco con l'etichetta «tu», e si annulla", async () => {
      const spy = renderQueue({
        pending: [],
        humanDecided: [
          deciso({ id: "h1", display_name: "Bottarga", decided_by: "human", decided_name: "bottarga" }),
        ],
      });

      expect(
        await screen.findByRole("heading", { name: "Decisioni recenti" })
      ).toBeInTheDocument();
      expect(screen.queryByText("Deciso dall'AI")).not.toBeInTheDocument();
      const riga = screen.getByText("Bottarga").closest("li")!;
      expect(riga).toHaveTextContent("tu");

      await userEvent.click(
        screen.getByRole("button", { name: /annulla la decisione su «Bottarga»/i })
      );
      await waitFor(() =>
        expect(
          spy.mock.calls.some(
            ([url, init]) =>
              String(url).includes("/imports/terms/h1/undo") &&
              (init as RequestInit | undefined)?.method === "POST"
          )
        ).toBe(true)
      );
      expect(await screen.findByText("Nessuna ricetta è tornata in coda.")).toBeInTheDocument();
    });

    it("un elenco solo, dalla decisione più recente, con chi ha deciso su ogni riga", async () => {
      renderQueue({
        pending: [],
        decided: [
          deciso({ id: "a1", display_name: "Rigatoni", decided_at: "2026-09-22T10:00:00Z" }),
          deciso({ id: "a2", display_name: "Acqua", decided_action: "ignored", decided_name: null, decided_at: "2026-09-20T10:00:00Z" }),
        ],
        humanDecided: [
          deciso({ id: "h1", display_name: "Bottarga", decided_by: "human", decided_at: "2026-09-23T10:00:00Z" }),
          deciso({ id: "h2", display_name: "Speck", decided_by: "human", decided_at: "2026-09-21T10:00:00Z" }),
        ],
      });

      await screen.findByText("Bottarga");
      const sezione = screen.getByRole("heading", { name: "Decisioni recenti" }).closest("section")!;
      const righe = within(sezione).getAllByRole("listitem");
      expect(righe).toHaveLength(4);
      ["Bottarga", "Rigatoni", "Speck", "Acqua"].forEach((nome, i) =>
        expect(within(righe[i]).getByText(nome)).toBeInTheDocument()
      );
      expect(righe.map((riga) => within(riga).getByTestId("decided-by").textContent)).toEqual([
        "tu", "AI", "tu", "AI",
      ]);
    });

    it("l'elenco fuso tiene lo stesso tetto di 50, e sono le 50 più recenti", async () => {
      // 30 dell'AI e 30 a mano, intercalate per data: dopo la fusione restano le 50
      // più recenti, non le prime 50 di un elenco e le altre in coda
      const giorno = (i: number) => new Date(Date.UTC(2026, 8, 1, 0, i)).toISOString();
      renderQueue({
        pending: [],
        decided: Array.from({ length: 30 }, (_, i) =>
          deciso({ id: `a${i}`, display_name: `ai-${i}`, decided_at: giorno(2 * i) })
        ),
        humanDecided: Array.from({ length: 30 }, (_, i) =>
          deciso({ id: `h${i}`, display_name: `mano-${i}`, decided_by: "human", decided_at: giorno(2 * i + 1) })
        ),
      });

      await screen.findByText("mano-29");
      const sezione = screen.getByRole("heading", { name: "Decisioni recenti" }).closest("section")!;
      expect(within(sezione).getAllByRole("listitem")).toHaveLength(50);
      // le dieci più vecchie (minuti 0–9) restano fuori
      expect(screen.queryByText("ai-4")).not.toBeInTheDocument();
      expect(screen.queryByText("mano-4")).not.toBeInTheDocument();
      expect(screen.getByText("ai-5")).toBeInTheDocument();
    });
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

  it("un giro dell'AI che non decide niente lo dice, nominando il lavoro rimasto", async () => {
    // Il caso che conta: `applied: 0` è un 200, non un guasto — il backend assorbe
    // ogni modello giù per termine e risponde comunque. Letto come "non è successo
    // niente" invece che "l'AI ha rinunciato su tutto", l'utente ripreme il
    // bottone: un'altra chiamata a pagamento. Il messaggio deve nominare i termini
    // rimasti, non fermarsi alla frase sull'sbloccato (che qui varrebbe zero
    // comunque e non distinguerebbe i due casi).
    renderQueue({
      askAiResult: [
        { applied: 0, created: 0, ignored: 0, still_pending: 2, unlocked: 0, remaining_terms: 2 },
        200,
      ],
    });

    await userEvent.click(await screen.findByRole("button", { name: /Riprova con l'AI/i }));

    expect(
      await screen.findByText(/non ha deciso nessuno dei 2 termini/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/si decidono a mano qui sotto/i)).toBeInTheDocument();
    expect(screen.getByText(/costa un'altra chiamata al modello/i)).toBeInTheDocument();
  });

  it("una decisione a mano dopo un giro dell'AI non mostra più i contatori dell'AI", async () => {
    // Lo stato è condiviso fra `askAi` e `decide`: senza distinguerli, un tocco a
    // mano dopo un giro dell'AI o resterebbe sulla frase dell'AI, o (peggio)
    // mostrerebbe i SUOI numeri come se fossero l'esito del tocco.
    renderQueue({
      askAiResult: [
        { applied: 1, created: 0, ignored: 0, still_pending: 1, unlocked: 3, remaining_terms: 1 },
        200,
      ],
    });

    await userEvent.click(await screen.findByRole("button", { name: /Riprova con l'AI/i }));
    await screen.findByText(/L'AI ha deciso/i);

    await userEvent.click(await screen.findByRole("button", { name: /Forse «pasta»/i }));

    await waitFor(() => expect(screen.getByText("Sbloccate 12 ricette.")).toBeInTheDocument());
    expect(screen.queryByText(/L'AI ha deciso/i)).not.toBeInTheDocument();
  });

  it("dalla coda dell'import si torna alle ricette con un tasto", async () => {
    // stessi stub del test accanto: qui interessa solo l'uscita
    renderQueue();

    expect((await screen.findByRole("link", { name: "Ricette" })).getAttribute("href"))
      .toBe("/ricette");
  });
});

describe("un termine messo a fuoco con ?termine=", () => {
  // deciso tanto tempo fa, e in automatico: in «Decisioni recenti» non c'è
  const VECCHIO: ImportTerm = {
    id: "t9", display_name: "Pomodori pelati", occurrences: 4, suggestion: null,
    waiting_titles: [], decided_by: "auto", decided_action: "map", decided_name: "pomodori",
    decided_at: "2026-01-02T10:00:00Z",
  };

  it("un termine deciso che le decisioni recenti non mostrano si vede in cima, e si annulla", async () => {
    const spy = renderQueue({ path: "/ricette/importa?termine=t9", focused: [VECCHIO, 200] });

    const cima = await screen.findByRole("region", { name: "Il termine che cercavi" });
    expect(within(cima).getByText("collegato a pomodori")).toBeInTheDocument();
    await userEvent.click(
      within(cima).getByRole("button", { name: "Annulla la decisione su «Pomodori pelati»" })
    );

    await waitFor(() =>
      expect(
        spy.mock.calls.some(
          ([url, init]) => String(url).endsWith("/imports/terms/t9/undo") && init?.method === "POST"
        )
      ).toBe(true)
    );
    // la coda resta sotto, com'è
    expect(screen.getByText("Rigatoni")).toBeInTheDocument();
  });

  it("un termine ancora in coda sta in cima una volta sola, e lì si decide", async () => {
    renderQueue({ path: "/ricette/importa?termine=t1", focused: [TERMINI[0], 200] });

    const cima = await screen.findByRole("region", { name: "Il termine che cercavi" });
    expect(within(cima).getByText("Rigatoni")).toBeInTheDocument();
    await screen.findByText("Acqua");
    expect(screen.getAllByText("Rigatoni")).toHaveLength(1);
  });

  it("un termine che non si trova lo dice in una riga, e la coda resta", async () => {
    renderQueue({ path: "/ricette/importa?termine=sparito" });

    expect(await screen.findByText(/Non trovo quel termine/)).toBeInTheDocument();
    expect(screen.getByText("Rigatoni")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Il termine che cercavi" })).not.toBeInTheDocument();
  });

  it("un guasto nel leggere il termine non si spaccia per «non c'è», e offre «Riprova»", async () => {
    // il predicato vero, senza l'attesa fra un tentativo e l'altro: il test guarda cosa
    // si dice dopo i tentativi, non quanto durano
    const client = new QueryClient({
      defaultOptions: { queries: { retry: defaultQueryRetryPredicate, retryDelay: 0 } },
    });
    const spy = renderQueue({
      path: "/ricette/importa?termine=t9", focused: [{ detail: "guasto" }, 500], client,
    });

    expect(await screen.findByText(/Non sono riuscito a leggere quel termine/)).toBeInTheDocument();
    expect(screen.queryByText(/Non trovo quel termine/)).not.toBeInTheDocument();
    expect(screen.getByText("Rigatoni")).toBeInTheDocument();
    const prima = spy.mock.calls.filter(([url]) => String(url).endsWith("/imports/terms/t9")).length;

    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));

    await waitFor(() =>
      expect(
        spy.mock.calls.filter(([url]) => String(url).endsWith("/imports/terms/t9")).length
      ).toBeGreaterThan(prima)
    );
  });

  it("senza ?termine= non chiede nessun termine per id", async () => {
    const spy = renderQueue();

    await screen.findByText("Rigatoni");
    expect(spy.mock.calls.some(([url]) => /\/imports\/terms\/[^/?]+$/.test(String(url)))).toBe(false);
  });
});
