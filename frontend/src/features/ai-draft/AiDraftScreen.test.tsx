import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AiDraftScreen } from "./AiDraftScreen";
import { RecipeBookScreen } from "../recipes/RecipeBookScreen";
import type { DraftIngredient } from "../../domain/types";

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

const CREATED = JSON.stringify({ ...DRAFT, id: "r9" });

function draftOk() {
  return vi.fn().mockResolvedValue(new Response(JSON.stringify(DRAFT), { status: 200 }));
}

function draftThenSave(saveResponse: Response) {
  return vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify(DRAFT), { status: 200 }))
    .mockResolvedValue(saveResponse);
}

function aiDown() {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ detail: "stesura AI non disponibile" }), { status: 503 })
  );
}

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

/** La bozza è arrivata quando il titolo proposto è nel campo. Prima di questo il
 * modulo è quello vuoto — c'è comunque, ed è il punto — e salvare salverebbe
 * un'altra cosa. */
async function draftLanded() {
  await screen.findByDisplayValue("Pasta al pomodoro");
}

function postedRecipe(spy: ReturnType<typeof vi.fn>) {
  const post = spy.mock.calls.find(
    ([url, init]) => String(url).endsWith("/recipes") && init?.method === "POST"
  );
  return JSON.parse(post![1].body);
}

// Apparato per il Task 14: finge una bozza con gli ingredienti passati e la
// mostra in pagina, riusando `proposeDraft`/`draftLanded`. Lo spy resta
// disponibile a `ultimoCorpoDiPost`, che legge l'ultima POST verso un dato
// percorso — qui serve per leggere cosa il salvataggio manda a `/recipes`.
let ultimoFetchSpy: ReturnType<typeof vi.fn> | null = null;

async function mostraBozzaCon(ingredients: DraftIngredient[]) {
  const bozza = { ...DRAFT, ingredients };
  const spy = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify(bozza), { status: 200 }))
    .mockResolvedValue(new Response(CREATED, { status: 201 }));
  vi.stubGlobal("fetch", spy);
  ultimoFetchSpy = spy;
  renderScreen();
  await proposeDraft();
  await draftLanded();
}

function ultimoCorpoDiPost(pathSuffix: string) {
  const spy = ultimoFetchSpy;
  if (spy === null) throw new Error("nessuno spy: chiama prima mostraBozzaCon");
  const posts = spy.mock.calls.filter(
    ([url, init]) => String(url).endsWith(pathSuffix) && init?.method === "POST"
  );
  const last = posts[posts.length - 1];
  return JSON.parse(last[1].body);
}

function saveButton() {
  return screen.getByRole("button", { name: "Salva nel ricettario" });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AiDraftScreen", () => {
  it("mostra la bozza proposta dal modello", async () => {
    vi.stubGlobal("fetch", draftOk());
    renderScreen();
    await proposeDraft();

    expect(await screen.findByDisplayValue("Pasta al pomodoro")).toBeDefined();
  });

  // m13: il modello può proporre due volte lo stesso nome — il prompt non lo vieta
  // e `draft_recipe` non deduplica. Con la chiave costruita sul solo `raw_name` le
  // due righe erano la stessa riga per React e per `updateLine`: spuntarne una
  // spuntava l'altra, e chi guardava vedeva due caselle muoversi insieme.
  it("due righe di bozza con lo stesso nome restano due righe indipendenti", async () => {
    const duplicated = {
      ...DRAFT,
      ingredients: [
        { raw_name: "pomodoro", role: "primary", quantity_text: "400 g",
          ingredient_id: "i1", matched_name: "pomodoro", confident: true },
        { raw_name: "pomodoro", role: "secondary", quantity_text: "2 cucchiai",
          ingredient_id: "i1", matched_name: "pomodoro", confident: true },
      ],
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(duplicated), { status: 200 })
    ));
    renderScreen();
    await proposeDraft();
    await draftLanded();

    const boxes = screen.getAllByRole("checkbox", { name: "Includi pomodoro" });
    expect(boxes).toHaveLength(2);

    await userEvent.click(boxes[0]);
    expect(boxes[0]).not.toBeChecked();
    expect(boxes[1]).toBeChecked();
  });

  // Il requisito fondante: "mai un vicolo cieco". Il modulo non è una conseguenza
  // di una richiesta riuscita né di una fallita — c'è e basta, perché
  // `createRecipe` non ha nessun altro punto di chiamata in tutta l'app.
  it("il modulo della ricetta è in pagina prima di qualsiasi richiesta all'AI", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderScreen();

    expect(screen.getByLabelText("Titolo")).toBeDefined();
    expect(screen.getByLabelText("Porzioni")).toBeDefined();
    expect(screen.getByLabelText("Procedimento")).toBeDefined();
    expect(screen.getByLabelText("Aggiungi un ingrediente")).toBeDefined();
    expect(saveButton()).toBeDefined();
  });

  // Titolo e procedimento sono gli unici due campi che il backend pretende non
  // vuoti. Un pulsante spento che non dice perché è un vicolo cieco anche lui:
  // il motivo sta accanto al pulsante, e sparisce quando non serve più.
  it("senza titolo o senza procedimento il salvataggio è spento, e dice cosa manca", async () => {
    vi.stubGlobal("fetch", vi.fn());
    renderScreen();

    expect(screen.getByText(/servono un titolo e un procedimento/i)).toBeDefined();
    expect(saveButton()).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Titolo"), "Cacio e pepe");
    expect(screen.getByText(/servono un titolo e un procedimento/i)).toBeDefined();
    expect(saveButton()).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Procedimento"), "1. Lessa.");
    expect(screen.queryByText(/servono un titolo e un procedimento/i)).toBeNull();
    expect(saveButton()).not.toBeDisabled();

    await userEvent.clear(screen.getByLabelText("Titolo"));
    expect(screen.getByText(/servono un titolo e un procedimento/i)).toBeDefined();
    expect(saveButton()).toBeDisabled();
  });

  it("segnala gli agganci incerti, perché la conferma spetta a te", async () => {
    vi.stubGlobal("fetch", draftOk());
    renderScreen();
    await proposeDraft();

    expect(await screen.findByText(/basilico.*da confermare/i)).toBeDefined();
  });

  // Decisione 2 del progetto: un aggancio sbagliato accettato in silenzio avvelena
  // la disponibilità di ogni ricetta che usa quell'ingrediente. Quindi parte
  // escluso, e la riga dice perché: una casella vuota senza spiegazione sarebbe
  // un'altra cosa da indovinare.
  it("un aggancio incerto parte escluso, e la riga dice perché", async () => {
    vi.stubGlobal("fetch", draftOk());
    renderScreen();
    await proposeDraft();
    await draftLanded();

    expect(await screen.findByLabelText(/includi basilico fresco/i)).not.toBeChecked();
    expect(screen.getByLabelText(/includi pasta/i)).toBeChecked();
    expect(screen.getByText(/spunta la casella se è quello giusto/i)).toBeDefined();
  });

  it("non salva gli ingredienti senza aggancio, e lo dice", async () => {
    vi.stubGlobal("fetch", draftOk());
    renderScreen();
    await proposeDraft();

    expect(await screen.findByText(/zafferano di Navelli.*non in anagrafica/i)).toBeDefined();
  });

  it("salva solo gli agganci confermati, con provenienza AI", async () => {
    const spy = draftThenSave(new Response(CREATED, { status: 201 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await draftLanded();
    await userEvent.click(saveButton());

    const body = postedRecipe(spy);
    expect(body.source).toBe("ai");
    // "basilico" è incerto e nessuno l'ha confermato: non entra
    expect(body.ingredients).toHaveLength(1);
    expect(body.ingredients[0].ingredient_id).toBe("i1");
  });

  it("un aggancio incerto entra nel salvataggio solo dopo la conferma", async () => {
    const spy = draftThenSave(new Response(CREATED, { status: 201 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await draftLanded();
    await userEvent.click(await screen.findByLabelText(/includi basilico fresco/i));
    await userEvent.click(saveButton());

    const body = postedRecipe(spy);
    expect(body.ingredients).toHaveLength(2);
    expect(body.ingredients.map((i: { ingredient_id: string }) => i.ingredient_id)).toEqual([
      "i1", "i2",
    ]);
  });

  it("anche un aggancio sicuro si può togliere, e una ricetta senza agganci lo dichiara", async () => {
    const spy = draftThenSave(new Response(CREATED, { status: 201 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await draftLanded();
    await userEvent.click(await screen.findByLabelText(/includi pasta/i));

    expect(screen.getByRole("status")).toHaveTextContent(/nessun ingrediente agganciato/i);

    await userEvent.click(saveButton());
    expect(postedRecipe(spy).ingredients).toHaveLength(0);
  });

  it("la quantità si corregge, ed è quella corretta che viene salvata", async () => {
    const spy = draftThenSave(new Response(CREATED, { status: 201 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await draftLanded();

    const quantity = screen.getByLabelText("Quantità per pasta");
    await userEvent.clear(quantity);
    await userEvent.type(quantity, "200 g");
    await userEvent.click(saveButton());

    expect(postedRecipe(spy).ingredients[0].quantity_text).toBe("200 g");
  });

  it("dichiara il guasto quando il servizio AI non risponde", async () => {
    vi.stubGlobal("fetch", aiDown());
    renderScreen();
    await proposeDraft();

    expect(await screen.findByRole("alert")).toBeDefined();
  });

  it("non perde il prompt scritto quando la stesura fallisce, così si può riprovare", async () => {
    vi.stubGlobal("fetch", aiDown());
    renderScreen();
    await proposeDraft();
    await screen.findByRole("alert");

    expect(screen.getByLabelText("Cosa vuoi cucinare")).toHaveValue("qualcosa di veloce");
  });

  // Il caso per cui questo schermo esiste: Claude giù, nessuna chiave, risposta
  // inutilizzabile. La promessa "scrivila a mano" deve essere vera, e la ricetta
  // che ne esce non è "ai": l'ha scritta una persona.
  it("quando la stesura AI fallisce, la ricetta si scrive a mano e si salva", async () => {
    const spy = vi.fn((url: RequestInfo | URL) =>
      String(url).includes("/recipes/ai-draft")
        ? Promise.resolve(
            new Response(JSON.stringify({ detail: "stesura AI non disponibile" }), { status: 503 })
          )
        : Promise.resolve(new Response(JSON.stringify({ id: "r10" }), { status: 201 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await screen.findByRole("alert");

    await userEvent.type(screen.getByLabelText("Titolo"), "Cacio e pepe");
    await userEvent.type(screen.getByLabelText("Procedimento"), "1. Lessa la pasta.");
    expect(screen.getByRole("status")).toHaveTextContent(/nessun ingrediente agganciato/i);

    await userEvent.click(saveButton());

    const body = postedRecipe(spy);
    expect(body.title).toBe("Cacio e pepe");
    expect(body.instructions).toBe("1. Lessa la pasta.");
    expect(body.source).toBe("manual");
    expect(body.source_ref).toBeNull();
    expect(body.ingredients).toHaveLength(0);
    // il prompt scritto è lavoro dell'utente, non dato ricaricabile: resta lì
    expect(screen.getByLabelText("Cosa vuoi cucinare")).toHaveValue("qualcosa di veloce");
  });

  it("un ingrediente si aggancia a mano, con il ruolo che scegli tu", async () => {
    const spy = vi.fn((url: RequestInfo | URL) =>
      String(url).includes("/ingredients/search")
        ? Promise.resolve(new Response(JSON.stringify([
            { id: "i7", name: "zafferano", display_name: "Zafferano", category: "spezie" },
          ]), { status: 200 }))
        : Promise.resolve(new Response(JSON.stringify({ id: "r11" }), { status: 201 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.type(screen.getByLabelText("Titolo"), "Risotto allo zafferano");
    await userEvent.type(screen.getByLabelText("Procedimento"), "1. Tosta il riso.");
    await userEvent.type(screen.getByLabelText("Aggiungi un ingrediente"), "zaff");

    await userEvent.click(await screen.findByRole("option", { name: /zafferano/i }));
    await userEvent.click(screen.getByRole("button", { name: "secondario" }));
    await userEvent.click(saveButton());

    const body = postedRecipe(spy);
    expect(body.source).toBe("manual");
    expect(body.ingredients).toEqual([
      { ingredient_id: "i7", role: "secondary", quantity_text: null },
    ]);
  });

  it("se la ricerca degli ingredienti non risponde, la ricetta si salva comunque", async () => {
    const spy = vi.fn((url: RequestInfo | URL) =>
      String(url).includes("/ingredients/search")
        ? Promise.resolve(new Response(JSON.stringify({ detail: "giù" }), { status: 500 }))
        : Promise.resolve(new Response(JSON.stringify({ id: "r12" }), { status: 201 }))
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await userEvent.type(screen.getByLabelText("Titolo"), "Minestra");
    await userEvent.type(screen.getByLabelText("Procedimento"), "1. Bolli.");
    await userEvent.type(screen.getByLabelText("Aggiungi un ingrediente"), "zaff");

    expect(await screen.findByRole("alert")).toHaveTextContent(/ricerca degli ingredienti/i);

    await userEvent.click(saveButton());
    expect(postedRecipe(spy).ingredients).toHaveLength(0);
  });

  // Le porzioni arrivano dal modello e il backend le vuole tra 1 e 50: senza un
  // campo, una bozza con "servings: 0" era un 422 senza niente da correggere.
  it("le porzioni fuori scala si correggono qui, invece di far rifiutare il salvataggio", async () => {
    const spy = vi.fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...DRAFT, servings: 0 }), { status: 200 })
      )
      .mockResolvedValue(new Response(CREATED, { status: 201 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await draftLanded();

    expect(await screen.findByText(/porzioni devono stare tra 1 e 50/i)).toBeDefined();
    expect(saveButton()).toBeDisabled();

    const servings = screen.getByLabelText("Porzioni");
    await userEvent.clear(servings);
    await userEvent.type(servings, "4");
    await userEvent.click(saveButton());

    expect(postedRecipe(spy).servings).toBe(4);
  });

  it("una porzione non scritta resta non scritta, non diventa un numero inventato", async () => {
    const spy = vi.fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...DRAFT, servings: null }), { status: 200 })
      )
      .mockResolvedValue(new Response(CREATED, { status: 201 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await draftLanded();

    expect(screen.getByLabelText("Porzioni")).toHaveValue("");
    await userEvent.click(saveButton());

    expect(postedRecipe(spy).servings).toBeNull();
  });

  it("una quantità troppo lunga si corregge prima di mandarla", async () => {
    const spy = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ...DRAFT,
        ingredients: [{ ...DRAFT.ingredients[0], quantity_text: "q".repeat(140) }],
      }), { status: 200 }))
      .mockResolvedValue(new Response(CREATED, { status: 201 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await draftLanded();

    expect(await screen.findByText(/quantità di «pasta» è troppo lunga/i)).toBeDefined();
    expect(saveButton()).toBeDisabled();

    await userEvent.clear(screen.getByLabelText("Quantità per pasta"));
    await userEvent.type(screen.getByLabelText("Quantità per pasta"), "180 g");
    await userEvent.click(saveButton());

    expect(postedRecipe(spy).ingredients[0].quantity_text).toBe("180 g");
  });

  it("un prompt lungo non fa rifiutare il salvataggio", async () => {
    const spy = draftThenSave(new Response(CREATED, { status: 201 }));
    vi.stubGlobal("fetch", spy);

    renderScreen();
    // il prompt può arrivare a 1000 caratteri, `source_ref` ne accetta 500
    fireEvent.change(screen.getByLabelText("Cosa vuoi cucinare"), {
      target: { value: "p".repeat(900) },
    });
    await userEvent.click(screen.getByRole("button", { name: "Proponi" }));
    await draftLanded();
    await userEvent.click(saveButton());

    expect(postedRecipe(spy).source_ref.length).toBeLessThanOrEqual(500);
  });

  // Un 422 e una rete che cade non sono la stessa cosa: rimandare gli stessi byte
  // dopo un 422 dà lo stesso 422, e dire "riprova" sarebbe un vicolo cieco
  // travestito da invito.
  it("un rifiuto di validazione non si traveste da guasto passeggero", async () => {
    const spy = draftThenSave(
      new Response(JSON.stringify({
        detail: [{ loc: ["body", "title"], msg: "troppo lungo", type: "string_too_long" }],
      }), { status: 422 })
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await draftLanded();
    await userEvent.click(saveButton());

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/rifiutato/i);
    expect(alert.textContent).not.toMatch(/riprova/i);
  });

  it("un salvataggio fallito lo dice accanto al pulsante, senza perdere la bozza corretta", async () => {
    const spy = draftThenSave(
      new Response(JSON.stringify({ detail: "errore" }), { status: 500 })
    );
    vi.stubGlobal("fetch", spy);

    renderScreen();
    await proposeDraft();
    await draftLanded();
    await userEvent.click(saveButton());

    expect(await screen.findByRole("alert")).toHaveTextContent(/non sono riuscito a salvare/i);
    // la bozza resta in pagina, pronta per un altro tentativo
    expect(screen.getByDisplayValue("Pasta al pomodoro")).toBeDefined();
  });

  it("un ingrediente ignoto si crea salvando, con la categoria modificabile", async () => {
    // usa l'apparato già presente in questo file per fingere la bozza: cerca come i
    // test esistenti servono POST /recipes/ai-draft e riusa quello
    await mostraBozzaCon([
      {
        raw_name: "speck", role: "primary", quantity_text: "100 g",
        ingredient_id: null, matched_name: null, confident: false,
        proposed_category: "carne",
      },
    ]);

    expect(await screen.findByText(/lo creo io salvando/i)).toBeInTheDocument();
    const categoria = screen.getByLabelText(/categoria per «speck»/i);
    expect(categoria).toHaveValue("carne");

    await userEvent.selectOptions(categoria, "pesce");
    await userEvent.click(screen.getByRole("button", { name: /salva/i }));

    // il corpo mandato porta nome e categoria, non un ingredient_id nullo che il
    // backend rifiuterebbe con un 422
    const corpo = ultimoCorpoDiPost("/recipes");
    expect(corpo.ingredients[0]).toMatchObject({ name: "speck", category: "pesce" });
    expect(corpo.ingredients[0].ingredient_id).toBeUndefined();
  });
});

// La chiave `["recipes"]` invalida per prefisso ogni voce `["recipes", termine,
// soloCucinabili]` del ricettario. Era vero per ispezione e per niente altro:
// qui i due schermi stanno sotto lo stesso QueryClient, e la ricerca deve
// ripartire da sé quando il salvataggio va a buon fine.
describe("AiDraftScreen e il ricettario sotto lo stesso QueryClient", () => {
  it("una ricetta salvata fa ripartire la ricerca del ricettario", async () => {
    const spy = vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
      const href = String(url);
      if (href.includes("/recipes/search"))
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      if (href.includes("/recipes/ai-draft"))
        return Promise.resolve(new Response(JSON.stringify(DRAFT), { status: 200 }));
      if (href.endsWith("/recipes") && init?.method === "POST")
        return Promise.resolve(new Response(CREATED, { status: 201 }));
      return Promise.resolve(new Response("{}", { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <AiDraftScreen />
          <RecipeBookScreen />
        </MemoryRouter>
      </QueryClientProvider>
    );

    const searches = () =>
      spy.mock.calls.filter(([url]) => String(url).includes("/recipes/search")).length;
    await vi.waitFor(() => expect(searches()).toBeGreaterThan(0));
    const before = searches();

    await proposeDraft();
    await draftLanded();
    await userEvent.click(saveButton());

    await vi.waitFor(() => expect(searches()).toBeGreaterThan(before));
  });
});
