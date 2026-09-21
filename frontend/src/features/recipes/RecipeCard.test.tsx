import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RecipeCard } from "./RecipeCard";
import type { RecipeSummary } from "../../domain/types";

function ricetta(overrides: Partial<RecipeSummary> = {}): RecipeSummary {
  return {
    id: "r1", title: "Pasta al pomodoro", description: "Di sempre", source: "dataset",
    missing: 0, cookable: true, missing_names: [], image_url: null,
    prep_minutes: null, cook_minutes: null, category: null,
    ...overrides,
  };
}

function renderCard(recipe: RecipeSummary) {
  return render(
    <MemoryRouter>
      <ul>
        <RecipeCard recipe={recipe} />
      </ul>
    </MemoryRouter>
  );
}

describe("RecipeCard", () => {
  it("elenca quel che manca", () => {
    renderCard(ricetta({ missing: 2, cookable: false, missing_names: ["Basilico", "Pomodoro"] }));
    expect(screen.getByText("Basilico, Pomodoro")).toBeVisible();
  });

  it("non dice niente quando non manca niente", () => {
    renderCard(ricetta());
    expect(screen.getByText("Puoi cucinarla ora")).toBeVisible();
    expect(screen.queryByText(/,/)).toBeNull();
  });

  it("taglia gli elenchi lunghi invece di allungare la riga", () => {
    renderCard(
      ricetta({
        missing: 5, cookable: false,
        missing_names: ["Acciughe", "Basilico", "Capperi", "Olive", "Pomodoro"],
      })
    );
    expect(screen.getByText("Acciughe, Basilico, Capperi e altri 2")).toBeVisible();
  });

  it("al singolare dice «un altro»", () => {
    renderCard(
      ricetta({
        missing: 4, cookable: false,
        missing_names: ["Acciughe", "Basilico", "Capperi", "Olive"],
      })
    );
    expect(screen.getByText("Acciughe, Basilico, Capperi e un altro")).toBeVisible();
  });
});
