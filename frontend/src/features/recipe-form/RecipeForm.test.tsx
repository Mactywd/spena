import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "../../api/client";
import { RecipeForm } from "./RecipeForm";
import { lineFromDraft, valuesFromRecipe, type RecipeFormValues } from "./formModel";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { RecipeBody, RecipeDetail } from "../../domain/types";

const DETAIL: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: "Di sempre", source: "manual",
  missing: 0, cookable: true, missing_names: [], image_url: null, prep_minutes: null,
  cook_minutes: null, category: "Primi piatti", cost: null, archived_at: null, main_department: null,
  instructions: "Cuoci.", servings: 2, source_ref: null, scaled_to: null,
  unscalable_lines: 0, dose_lines: 1, owned_by_import: false,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "320 g",
      quantity_display: "320 g", quantity_scaled: false, note: "al dente",
      availability: "available", satisfied: true },
    { ingredient_id: "i2", ingredient_name: "basilico", role: "secondary", quantity_text: null,
      quantity_display: null, quantity_scaled: false, note: null,
      availability: "missing", satisfied: false },
  ],
};

/** Il modulo è controllato: chi lo usa tiene i valori, come fanno le due schermate. */
function Genitore({
  initial,
  save,
}: {
  initial: RecipeFormValues;
  save: (body: RecipeBody) => Promise<RecipeDetail>;
}) {
  const [values, setValues] = useState(initial);
  return (
    <RecipeForm
      values={values}
      onChange={setValues}
      save={save}
      onSaved={() => {}}
      submitLabel="Salva le modifiche"
    />
  );
}

function renderForm(
  initial: RecipeFormValues,
  // quel che torna non conta qui: `onSaved` è vuoto, e il corpo mandato lo legge il test
  save = vi.fn((_body: RecipeBody) => Promise.resolve(DETAIL))
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Genitore initial={initial} save={save} />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { save, client };
}

function stubCategories([body, status]: [unknown, number]) {
  const spy = vi.fn((url: unknown) =>
    Promise.resolve(
      String(url).includes("/recipes/categories")
        ? new Response(JSON.stringify(body), { status })
        : new Response("[]", { status: 200 })
    )
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

async function salva() {
  await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RecipeForm riempito da una ricetta", () => {
  it("parte dai suoi valori, descrizione e categoria comprese", () => {
    stubCategories([[], 200]);
    renderForm(valuesFromRecipe(DETAIL));

    expect(screen.getByLabelText("Titolo")).toHaveValue("Pasta al pomodoro");
    expect(screen.getByLabelText("Descrizione")).toHaveValue("Di sempre");
    expect(screen.getByText("Primi piatti")).toBeInTheDocument();
    expect(screen.getByLabelText("Quantità per pasta")).toHaveValue("320 g");
  });

  it("una riga si toglie con la ✕, il ruolo si cambia, e la nota resta", async () => {
    stubCategories([[], 200]);
    const { save } = renderForm(valuesFromRecipe(DETAIL));

    await userEvent.click(screen.getByRole("button", { name: "Togli basilico" }));
    await userEvent.click(
      within(screen.getByRole("group", { name: "Ruolo di pasta" })).getByRole("button", {
        name: "secondario",
      })
    );
    await salva();

    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        ingredients: [{ ingredient_id: "i1", role: "secondary", quantity_text: "320 g", note: "al dente" }],
      })
    );
  });

  it("il nome di una riga si legge una volta sola", () => {
    stubCategories([[], 200]);
    renderForm(valuesFromRecipe(DETAIL));
    expect(screen.getAllByText("pasta")).toHaveLength(1);
  });

  it("il ruolo si cambia anche su una riga proposta dall'AI", async () => {
    stubCategories([[], 200]);
    const { save } = renderForm({
      ...valuesFromRecipe(DETAIL),
      lines: [
        lineFromDraft(
          { raw_name: "pasta", role: "primary", quantity_text: "180 g", ingredient_id: "i1",
            matched_name: "pasta", confident: true, proposed_category: null },
          0
        ),
      ],
    });

    await userEvent.click(
      within(screen.getByRole("group", { name: "Ruolo di pasta" })).getByRole("button", {
        name: "secondario",
      })
    );
    await salva();

    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        ingredients: [{ ingredient_id: "i1", role: "secondary", quantity_text: "180 g" }],
      })
    );
  });
});

describe("la categoria", () => {
  it("si apre, legge le categorie del ricettario, e si sceglie o si toglie", async () => {
    stubCategories([["Dolci", "Primi piatti"], 200]);
    const { save } = renderForm(valuesFromRecipe(DETAIL));

    await userEvent.click(screen.getByRole("button", { name: "Cambia la categoria" }));
    // «Categoria» è l'etichetta vera dell'elenco, non solo una scritta accanto
    expect(await screen.findByRole("listbox", { name: "Categoria" })).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("option", { name: "Dolci" }));
    expect(screen.getByText("Dolci")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Cambia la categoria" }));
    await userEvent.click(await screen.findByRole("option", { name: "Nessuna" }));
    await salva();

    expect(save).toHaveBeenCalledWith(expect.objectContaining({ category: null }));
  });

  it("scelta una categoria, il fuoco torna al bottone che apre la scelta", async () => {
    // l'opzione toccata sparisce con l'elenco: senza, il fuoco cadrebbe sul `body` e chi
    // naviga da tastiera o con lo screen reader ripartirebbe dall'inizio della pagina
    stubCategories([["Dolci", "Primi piatti"], 200]);
    renderForm(valuesFromRecipe(DETAIL));

    await userEvent.click(screen.getByRole("button", { name: "Cambia la categoria" }));
    await userEvent.click(await screen.findByRole("option", { name: "Dolci" }));

    expect(screen.getByRole("button", { name: "Cambia la categoria" })).toHaveFocus();
  });

  it(
    "se le categorie non arrivano lo dice, e la ricetta si salva lo stesso",
    async () => {
      // un 500 si ritenta due volte col predicato vero: da qui il tempo lungo
      stubCategories([{ detail: "giù" }, 500]);
      const { save } = renderForm(valuesFromRecipe(DETAIL));

      await userEvent.click(screen.getByRole("button", { name: "Cambia la categoria" }));
      expect(
        await screen.findByText(/la ricetta si salva anche senza/i, undefined, { timeout: 8000 })
      ).toBeInTheDocument();
      await salva();

      expect(save).toHaveBeenCalledWith(expect.objectContaining({ category: "Primi piatti" }));
    },
    10000
  );
});

describe("un salvataggio rifiutato", () => {
  it("con la sua frase la mostra com'è, e un 422 fa rileggere le categorie", async () => {
    stubCategories([["Primi piatti"], 200]);
    const frase =
      "«Primi piatti» non è una categoria del ricettario: scegline una dall'elenco, o nessuna.";
    const { client } = renderForm(
      valuesFromRecipe(DETAIL),
      vi.fn(() => Promise.reject(new ApiError(frase, 422, { detail: frase })))
    );
    // la scelta aperta una volta: la query delle categorie esiste, e si può invalidare
    await userEvent.click(screen.getByRole("button", { name: "Cambia la categoria" }));
    await userEvent.click(await screen.findByRole("option", { name: "Primi piatti" }));

    await salva();

    expect(await screen.findByRole("alert")).toHaveTextContent(frase);
    expect(client.getQueryState(["recipe-categories"])?.isInvalidated).toBe(true);
  });

  it("con un elenco di errori di validazione non lo mostra grezzo, e non dice «riprova»", async () => {
    stubCategories([[], 200]);
    renderForm(
      valuesFromRecipe(DETAIL),
      vi.fn(() =>
        Promise.reject(
          new ApiError("troppo lungo", 422, { detail: [{ loc: ["body", "title"], msg: "troppo lungo" }] })
        )
      )
    );

    await salva();

    const avviso = await screen.findByRole("alert");
    expect(avviso).toHaveTextContent(/rifiutato/);
    expect(avviso.textContent).not.toMatch(/riprova/i);
  });
});
