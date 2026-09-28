import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { RecipeEditScreen } from "./RecipeEditScreen";
import { RecipeDetailScreen } from "../cooking/RecipeDetailScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { RecipeDetail } from "../../domain/types";

const DETAIL: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: null, source: "manual",
  missing: 1, cookable: false, missing_names: ["Basilico"], image_url: null,
  prep_minutes: null, cook_minutes: null, category: null, cost: null, archived_at: null,
  instructions: "Cuoci.", servings: 2, source_ref: null, scaled_to: null,
  unscalable_lines: 0, dose_lines: 1, owned_by_import: false,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "180 g",
      quantity_display: "180 g", quantity_scaled: false, note: null,
      availability: "available", satisfied: true },
    { ingredient_id: "i2", ingredient_name: "basilico", role: "primary", quantity_text: null,
      quantity_display: null, quantity_scaled: false, note: null,
      availability: "missing", satisfied: false },
  ],
};

type Rotta = (path: string, init?: RequestInit) => [unknown, number] | undefined;

function stubFetch(route: Rotta = () => undefined) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    const [body, status] =
      route(path, init) ?? (path.includes("/pantry") ? [[], 200] : [DETAIL, 200]);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderEdit() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/ricette/r1/modifica"]}>
        <Routes>
          <Route path="/ricette/:id/modifica" element={<RecipeEditScreen />} />
          <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("la modifica di una ricetta (R10 §6.2)", () => {
  it("parte dalla ricetta, e una importata dice cosa succede salvando", async () => {
    stubFetch(() => [{ ...DETAIL, owned_by_import: true }, 200]);
    renderEdit();

    expect(await screen.findByDisplayValue("Pasta al pomodoro")).toBeInTheDocument();
    expect(screen.getByText(/salvando diventa tua, e l'import non la riscriverà più/i)).toBeInTheDocument();
  });

  it("una ricetta scritta qui non porta l'avviso", async () => {
    stubFetch();
    renderEdit();

    await screen.findByDisplayValue("Pasta al pomodoro");
    expect(screen.queryByText(/salvando diventa tua/i)).toBeNull();
  });

  it("salvare manda la PUT senza la riga tolta, e torna al dettaglio con «Salvata»", async () => {
    let salvata = DETAIL;
    const spy = stubFetch((path, init) => {
      if (init?.method === "PUT") {
        salvata = { ...DETAIL, missing: 0, cookable: true, missing_names: [], ingredients: [DETAIL.ingredients[0]] };
        return [salvata, 200];
      }
      if (path.endsWith("/recipes/r1")) return [salvata, 200];
      return undefined;
    });
    renderEdit();

    await screen.findByDisplayValue("Pasta al pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Togli basilico" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Salvata.");
    const put = spy.mock.calls.find(([, init]) => init?.method === "PUT")!;
    expect(String(put[0])).toBe("/api/v1/recipes/r1");
    const corpo = JSON.parse(String(put[1]!.body));
    expect(corpo.ingredients).toEqual([{ ingredient_id: "i1", role: "primary", quantity_text: "180 g" }]);
    // la provenienza non si manda: non si cambia
    expect(corpo.source).toBeUndefined();
  });

  it("una ricetta eliminata non si modifica: dice dove ripristinarla", async () => {
    stubFetch(() => [{ ...DETAIL, archived_at: "2026-09-28T10:00:00Z" }, 200]);
    renderEdit();

    expect(await screen.findByText(/ripristinala dalla sua pagina/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Vai alla ricetta" })).toHaveAttribute("href", "/ricette/r1");
    expect(screen.queryByRole("button", { name: "Salva le modifiche" })).toBeNull();
  });

  it("se nel frattempo è stata eliminata, il rifiuto lo dice con le sue parole", async () => {
    stubFetch((_path, init) =>
      init?.method === "PUT"
        ? [{ detail: "Questa ricetta è stata eliminata: ripristinala prima di modificarla." }, 409]
        : undefined
    );
    renderEdit();

    await screen.findByDisplayValue("Pasta al pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Questa ricetta è stata eliminata: ripristinala prima di modificarla."
    );
  });
});
