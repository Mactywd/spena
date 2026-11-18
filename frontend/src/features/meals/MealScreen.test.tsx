import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { createTestQueryClient } from "../../test/queryClient";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { MealScreen } from "./MealScreen";
import type { DishChat, Meal, RecipeDetail } from "../../domain/types";

function meal(extra: Partial<Meal> = {}): Meal {
  return {
    id: "m1", day: "2026-11-10", slot: "dinner", week: "2026-11-09", dish: "Pollo arrosto",
    sides: "piadina · banana", away: false, status: "official", unrecorded: false,
    recipe: null, leftover_of: null, ...extra,
  };
}

type Handler = (url: string, init?: RequestInit) => [unknown, number];

function stubFetch(handler: Handler) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = handler(String(url), init);
    return Promise.resolve(
      status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status })
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function calls(spy: ReturnType<typeof stubFetch>, method: string) {
  return spy.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === method)
    .map(([url, init]) => ({ url: String(url), body: (init as RequestInit).body ? JSON.parse(String((init as RequestInit).body)) : null }));
}

function renderMeal() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <NoticeProvider>
        <MemoryRouter initialEntries={["/pasti/m1"]}>
          <Routes>
            <Route path="/pasti" element={<p>la settimana</p>} />
            <Route path="/pasti/cambi/:id" element={<p>la scheda</p>} />
            <Route path="/pasti/:id" element={<MealScreen />} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

function recipeDetail(extra: Partial<RecipeDetail> = {}): RecipeDetail {
  return {
    id: "r1", title: "Pollo al limone", description: null, source: "manual",
    missing: 0, cookable: true, missing_names: [], image_url: null, prep_minutes: null, cook_minutes: null,
    category: null, cost: null, archived_at: null, main_department: null, instructions: "Cuoci il pollo.",
    servings: 2, source_ref: null, scaled_to: null, owned_by_import: false, derived_from: null,
    unscalable_lines: 0, dose_lines: 0, anchor: null, ingredients: [],
    in_book: false,
    meal: { id: "m1", day: "2026-11-10", slot: "dinner", dish: "Pollo arrosto", recipe_id: "r1" },
    ...extra,
  };
}

/** Il pasto su `/meals/…`, la ricetta su `/recipes/<id>` (anche la `PATCH`), il resto vuoto. */
function withRecipe(m: Meal, recipes: Record<string, RecipeDetail>): Handler {
  return (url) => {
    const found = Object.entries(recipes).find(([id]) => url.includes(`/recipes/${id}`));
    if (found) return [found[1], 200];
    if (url.includes("/meals/")) return [m, 200];
    return [[], 200];
  };
}

const reads = (m: Meal): Handler => (_url, init) => (init?.method ? [m, 200] : [m, 200]);

afterEach(() => vi.unstubAllGlobals());

describe("la schermata del piatto", () => {
  it("mostra posto, piatto e accompagnamenti", async () => {
    stubFetch(reads(meal()));
    renderMeal();
    expect(await screen.findByRole("heading", { level: 1, name: "Pollo arrosto" })).toBeInTheDocument();
    expect(screen.getByText("martedì 10 novembre · Cena")).toBeInTheDocument();
    expect(screen.getByText("piadina · banana")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Pasti/ })).toHaveAttribute("href", "/pasti?settimana=2026-11-09");
  });

  it("«Correggi» con il giorno cambiato manda solo `day` e chiude il modulo", async () => {
    const spy = stubFetch(reads(meal()));
    renderMeal();
    await userEvent.click(await screen.findByRole("button", { name: "Correggi" }));
    const day = screen.getByLabelText("Giorno");
    fireEvent.change(day, { target: { value: "2026-11-12" } });
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));
    await vi.waitFor(() => expect(calls(spy, "PATCH")).toHaveLength(1));
    expect(calls(spy, "PATCH")[0].body).toEqual({ day: "2026-11-12" });
    await vi.waitFor(() => expect(screen.queryByLabelText("Giorno")).toBeNull());
  });

  it("spostare su un posto occupato chiede «Sostituisci» e rimanda con replace", async () => {
    let first = true;
    const spy = stubFetch((_url, init) => {
      if (init?.method !== "PATCH") return [meal(), 200];
      if (first) {
        first = false;
        return [{ detail: "C'è già «Pizza» in questo posto.", code: "slot_taken" }, 409];
      }
      return [meal({ slot: "lunch" }), 200];
    });
    renderMeal();
    await userEvent.click(await screen.findByRole("button", { name: "Correggi" }));
    await userEvent.selectOptions(screen.getByLabelText("Pasto"), "lunch");
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));
    expect(await screen.findByText("C'è già «Pizza» in questo posto.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sostituisci" }));
    await vi.waitFor(() => expect(calls(spy, "PATCH")).toHaveLength(2));
    expect(calls(spy, "PATCH")[1].body).toEqual({ slot: "lunch", replace: true });
  });

  it("cambiare giorno dopo un posto occupato toglie la domanda: «Sostituisci» non cancella un pasto mai confermato", async () => {
    const spy = stubFetch((_url, init) =>
      init?.method === "PATCH"
        ? [{ detail: "C'è già «Pizza» in questo posto.", code: "slot_taken" }, 409]
        : [meal(), 200]
    );
    renderMeal();
    await userEvent.click(await screen.findByRole("button", { name: "Correggi" }));
    await userEvent.selectOptions(screen.getByLabelText("Pasto"), "lunch");
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));
    expect(await screen.findByText("C'è già «Pizza» in questo posto.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Giorno"), { target: { value: "2026-11-12" } });
    expect(screen.queryByText("C'è già «Pizza» in questo posto.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Sostituisci" })).toBeNull();
    expect(calls(spy, "PATCH")).toHaveLength(1);
  });

  it("«Elimina» con una ricetta fuori dal ricettario lo dice, poi torna alla settimana", async () => {
    const spy = stubFetch((_url, init) =>
      init?.method === "DELETE" ? [null, 204] : [meal({ recipe: { id: "r1", title: "Pollo", in_book: false } }), 200]
    );
    renderMeal();
    await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));
    expect(screen.getByText("Eliminare «Pollo arrosto»?")).toBeInTheDocument();
    expect(screen.getByText("La sua ricetta non è nel ricettario: si elimina con il pasto.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sì, elimina" }));
    expect(await screen.findByText("la settimana")).toBeInTheDocument();
    expect(screen.getByText("Pasto eliminato.")).toBeInTheDocument();
    expect(calls(spy, "DELETE")).toHaveLength(1);
  });

  it("una ricetta nel ricettario non porta la frase della ricetta", async () => {
    stubFetch(reads(meal({ recipe: { id: "r1", title: "Pollo", in_book: true } })));
    renderMeal();
    await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));
    expect(screen.queryByText(/non è nel ricettario/)).toBeNull();
  });

  it("una bozza ha «Rendi ufficiale», che manda `status: official`", async () => {
    const spy = stubFetch(reads(meal({ status: "draft" })));
    renderMeal();
    expect(await screen.findByText("È una bozza: la ricetta arriva quando diventa ufficiale.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Rendi ufficiale" }));
    await vi.waitFor(() => expect(calls(spy, "PATCH")).toHaveLength(1));
    expect(calls(spy, "PATCH")[0].body).toEqual({ status: "official" });
  });

  it("con la ricetta in preparazione: l'attesa al posto dei pulsanti", async () => {
    stubFetch(reads(meal({ recipe_state: "preparing", can_ask_recipe: false })));
    renderMeal();
    const wait = await screen.findByText("Ricetta in preparazione: arriva fra poco.");
    expect(wait.closest("[aria-live]")).toHaveAttribute("aria-live", "polite");
    expect(screen.queryByRole("link", { name: "Scrivi la ricetta" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Chiedi la ricetta a Claude" })).toBeNull();
  });

  it("la ricetta fallita: l'avviso e tre strade; «Chiedi la ricetta a Claude» manda la richiesta", async () => {
    const spy = stubFetch((url, init) =>
      init?.method === "POST"
        ? [meal({ recipe_state: "preparing" }), 202]
        : (reads(meal({
            recipe_state: "failed", can_ask_recipe: true,
            recipe_notice: "Claude non risponde: hai raggiunto il limite del piano.",
          }))(url, init))
    );
    renderMeal();
    expect(await screen.findByText("Claude non risponde: hai raggiunto il limite del piano.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Scrivi la ricetta" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Scegli dal ricettario" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Chiedi la ricetta a Claude" }));
    await vi.waitFor(() => expect(calls(spy, "POST")).toHaveLength(1));
    expect(calls(spy, "POST")[0].url).toBe("/api/v1/meals/m1/recipe/ask");
    expect(await screen.findByText("Ricetta chiesta a Claude.")).toBeInTheDocument();
  });

  it("un 503 sulla richiesta mostra il motivo e i pulsanti restano", async () => {
    stubFetch((url, init) =>
      init?.method === "POST"
        ? [{ code: "claude_not_configured", detail: "Claude non è collegato." }, 503]
        : (reads(meal({ can_ask_recipe: true }))(url, init))
    );
    renderMeal();
    await userEvent.click(await screen.findByRole("button", { name: "Chiedi la ricetta a Claude" }));
    expect(await screen.findByText("Claude non è collegato.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Chiedi la ricetta a Claude" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Scrivi la ricetta" })).toBeInTheDocument();
  });

  it("un pasto con una scheda aperta ha il collegamento alla scheda", async () => {
    stubFetch(reads(meal({ open_card_id: "c9" })));
    renderMeal();
    expect(await screen.findByRole("link", { name: "Scheda dei cambi da applicare" })).toHaveAttribute(
      "href",
      "/pasti/cambi/c9"
    );
  });

  it("«Rendi ufficiale» con una scheda nella risposta porta alla scheda", async () => {
    const spy = stubFetch((url, init) =>
      init?.method === "PATCH"
        ? [meal({ open_card_id: "c9" }), 200]
        : (reads(meal({ status: "draft" }))(url, init))
    );
    renderMeal();
    await userEvent.click(await screen.findByRole("button", { name: "Rendi ufficiale" }));
    await vi.waitFor(() => expect(calls(spy, "PATCH")).toHaveLength(1));
    expect(await screen.findByText("la scheda")).toBeInTheDocument();
  });

  it("un pasto ufficiale senza ricetta offre le due strade; fuori casa nessuna", async () => {
    stubFetch(reads(meal()));
    const first = renderMeal();
    expect(await screen.findByText("Questo pasto non ha ancora una ricetta.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Scrivi la ricetta" })).toHaveAttribute("href", "/pasti/m1/ricetta/nuova");
    expect(screen.getByRole("link", { name: "Scegli dal ricettario" })).toHaveAttribute("href", "/pasti/m1/ricetta/scegli");
    first.unmount();

    stubFetch(reads(meal({ away: true })));
    renderMeal();
    expect(await screen.findByText("Fuori casa: non c'è niente da cucinare.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Scrivi la ricetta" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Scegli dal ricettario" })).toBeNull();
    expect(within(document.body).queryByText("Scegli dal ricettario")).toBeNull();
  });

  describe("la ricetta nel piatto", () => {
    const withR = () => meal({ recipe: { id: "r1", title: "Pollo al limone", in_book: false } });

    it("il titolo della ricetta è un h2 e non c'è «Cucina»", async () => {
      stubFetch(withRecipe(withR(), { r1: recipeDetail() }));
      renderMeal();
      expect(await screen.findByRole("heading", { level: 2, name: "Pollo al limone" })).toBeInTheDocument();
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      expect(screen.queryByRole("button", { name: "Cucina" })).toBeNull();
    });

    it("«Modifica» porta al modulo con `?pasto=`; niente «Modifica con AI» né «Elimina» della ricetta", async () => {
      stubFetch(withRecipe(withR(), { r1: recipeDetail() }));
      renderMeal();
      const toolbar = await screen.findByRole("toolbar", { name: "Azioni della ricetta" });
      expect(within(toolbar).getByRole("link", { name: "Modifica" })).toHaveAttribute(
        "href", "/ricette/r1/modifica?pasto=m1"
      );
      expect(screen.queryByRole("button", { name: "Modifica con AI" })).toBeNull();
      expect(within(toolbar).queryByRole("button", { name: "Elimina" })).toBeNull();
    });

    it("«Salva nel ricettario» manda `in_book: true` e lo dice", async () => {
      const spy = stubFetch(withRecipe(withR(), { r1: recipeDetail() }));
      renderMeal();
      await userEvent.click(await screen.findByRole("button", { name: "Salva nel ricettario" }));
      await vi.waitFor(() => expect(calls(spy, "PATCH")).toHaveLength(1));
      expect(calls(spy, "PATCH")[0]).toEqual({ url: "/api/v1/recipes/r1", body: { in_book: true } });
      expect(await screen.findByText("Salvata nel ricettario.")).toBeInTheDocument();
    });

    it("se «Salva nel ricettario» fallisce, lo dice con le parole del server", async () => {
      stubFetch((url, init) =>
        init?.method === "PATCH" && url.includes("/recipes/r1")
          ? [{ detail: "Questa ricetta non ha più un pasto.", code: "no_meal" }, 409]
          : withRecipe(withR(), { r1: recipeDetail() })(url, init)
      );
      renderMeal();
      await userEvent.click(await screen.findByRole("button", { name: "Salva nel ricettario" }));
      expect(await screen.findByText("Questa ricetta non ha più un pasto.")).toBeInTheDocument();
    });

    it("con la ricetta nel ricettario c'è «Togli dal ricettario»", async () => {
      const spy = stubFetch(
        withRecipe(
          meal({ recipe: { id: "r1", title: "Pollo al limone", in_book: true } }),
          { r1: recipeDetail({ in_book: true }) }
        )
      );
      renderMeal();
      await userEvent.click(await screen.findByRole("button", { name: "Togli dal ricettario" }));
      await vi.waitFor(() => expect(calls(spy, "PATCH")).toHaveLength(1));
      expect(calls(spy, "PATCH")[0].body).toEqual({ in_book: false });
      expect(await screen.findByText("Tolta dal ricettario.")).toBeInTheDocument();
    });

    it("un avanzo rimanda al pasto d'origine e mostra la sua ricetta in sola lettura", async () => {
      const leftover = meal({
        id: "m2",
        leftover_of: { id: "m0", day: "2026-11-10", slot: "dinner", dish: "Frittata di spinaci", recipe_id: "r1" },
      });
      stubFetch(withRecipe(leftover, { r1: recipeDetail() }));
      renderMeal();
      const link = await screen.findByRole("link", {
        name: "Avanzo di «Frittata di spinaci», martedì 10 novembre · Cena",
      });
      expect(link).toHaveAttribute("href", "/pasti/m0");
      expect(await screen.findByRole("heading", { level: 2, name: "Pollo al limone" })).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "Modifica" })).toBeNull();
      expect(screen.queryByRole("button", { name: "Salva nel ricettario" })).toBeNull();
    });

    it("un avanzo la cui origine non ha ricetta lo dice", async () => {
      const leftover = meal({
        leftover_of: { id: "m0", day: "2026-11-10", slot: "dinner", dish: "Pizza", recipe_id: null },
      });
      stubFetch(withRecipe(leftover, {}));
      renderMeal();
      expect(await screen.findByText("Il pasto da cui viene non ha una ricetta.")).toBeInTheDocument();
    });
  });
});

describe("la chat sotto la ricetta del piatto", () => {
  const chatData = (extra: Partial<DishChat> = {}): DishChat => ({
    meal_id: "m1", conversation_id: "k1", messages: [], replying: false, highlight: null,
    claude_ready: true, claude_notice: null, ...extra,
  });
  const line = (id: string, name: string) => ({
    ingredient_id: id, ingredient_name: name, role: "primary" as const, quantity_text: "200 g",
    quantity_display: "200 g", quantity_scaled: false, anchorable: false, anchor_unit: null,
    note: null, availability: "available" as const, satisfied: true,
  });
  const withChat = (m: Meal, data: DishChat, recipe?: RecipeDetail): Handler => (url) => {
    if (url.includes("/chat")) return [data, 200];
    if (recipe && url.includes("/recipes/r1")) return [recipe, 200];
    if (url.includes("/meals/")) return [m, 200];
    return [[], 200];
  };
  const cooking = () =>
    meal({ can_chat: true, recipe: { id: "r1", title: "Pollo al limone", in_book: false } });

  it("con `can_chat` e una ricetta: «Chat con Claude» e il campo «Messaggio per Claude»", async () => {
    stubFetch(withChat(cooking(), chatData(), recipeDetail()));
    renderMeal();
    expect(await screen.findByRole("heading", { name: "Chat con Claude" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Messaggio per Claude" })).toBeInTheDocument();
  });

  it("fuori casa (`can_chat: false`) non c'è la chat", async () => {
    stubFetch(withChat(meal({ can_chat: false, away: true }), chatData()));
    renderMeal();
    await screen.findByRole("heading", { level: 1, name: "Pollo arrosto" });
    expect(screen.queryByRole("heading", { name: "Chat con Claude" })).toBeNull();
    expect(screen.queryByRole("textbox", { name: "Messaggio per Claude" })).toBeNull();
  });

  it("le righe che Claude ha cambiato portano `data-changed`, le altre no", async () => {
    const detail = recipeDetail({ ingredients: [line("i1", "spinaci"), line("i2", "pasta")] });
    stubFetch(
      withChat(
        cooking(),
        chatData({ highlight: { ingredient_ids: ["i1"], title: false, servings: false, instructions: false, description: false } }),
        detail
      )
    );
    renderMeal();
    const spinaci = (await screen.findByText("Spinaci")).closest("li")!;
    const pasta = screen.getByText("Pasta").closest("li")!;
    await vi.waitFor(() => expect(spinaci).toHaveAttribute("data-changed"));
    expect(pasta).not.toHaveAttribute("data-changed");
    expect(within(spinaci).getByText("(cambiata)")).toBeInTheDocument();
  });

  it("la tinta della riga cambiata sta sulla sua prima linea, non sul `<li>` che porta i pannelli", async () => {
    const detail = recipeDetail({ ingredients: [line("i1", "spinaci"), line("i2", "pasta")] });
    stubFetch(
      withChat(
        cooking(),
        chatData({ highlight: { ingredient_ids: ["i1"], title: false, servings: false, instructions: false, description: false } }),
        detail
      )
    );
    renderMeal();
    const spinaci = (await screen.findByText("Spinaci")).closest("li")!;
    await vi.waitFor(() => expect(spinaci).toHaveAttribute("data-changed"));
    expect(spinaci).not.toHaveClass("bg-brand-tint");
    expect(spinaci.firstElementChild).toHaveClass("bg-brand-tint");
  });

  it("senza ricetta, la chat sta insieme a «Scrivi la ricetta» e alla riga d'aiuto", async () => {
    stubFetch(withChat(meal({ can_chat: true }), chatData()));
    renderMeal();
    expect(await screen.findByRole("link", { name: "Scrivi la ricetta" })).toBeInTheDocument();
    expect(
      await screen.findByText("Chiedi a Claude di scrivere la ricetta di questo piatto.")
    ).toBeInTheDocument();
  });
});
