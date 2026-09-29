import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RecipeRow } from "./RecipeRow";
import type { RecipeSummary } from "../../domain/types";

function ricetta(overrides: Partial<RecipeSummary> = {}): RecipeSummary {
  return {
    id: "r1", title: "Pasta al pomodoro", description: "Di sempre", source: "dataset",
    missing: 0, cookable: true, missing_names: [], image_url: null,
    prep_minutes: null, cook_minutes: null, category: null, cost: null,
    archived_at: null, main_department: null,
    ...overrides,
  };
}

function renderRow(recipe: RecipeSummary) {
  return render(
    <MemoryRouter>
      <ul>
        <RecipeRow recipe={recipe} />
      </ul>
    </MemoryRouter>
  );
}

describe("RecipeRow", () => {
  it("quando si può cucinare dice «Hai tutto», e nessun nome", () => {
    renderRow(ricetta());
    expect(screen.getByText("Hai tutto")).toBeVisible();
    expect(screen.queryByText(/Manca/)).toBeNull();
  });

  it("altrimenti dice «Manca:» coi nomi di quel che manca", () => {
    renderRow(ricetta({ missing: 2, cookable: false, missing_names: ["Basilico", "Pomodoro"] }));
    expect(screen.getByText("Manca: Basilico, Pomodoro")).toBeVisible();
  });

  it("esattamente al limite non taglia: tre nomi restano tre nomi", () => {
    renderRow(ricetta({
      missing: 3, cookable: false, missing_names: ["Acciughe", "Basilico", "Capperi"],
    }));
    expect(screen.getByText("Manca: Acciughe, Basilico, Capperi")).toBeVisible();
  });

  it("taglia gli elenchi lunghi invece di allungare la riga", () => {
    renderRow(ricetta({
      missing: 5, cookable: false,
      missing_names: ["Acciughe", "Basilico", "Capperi", "Olive", "Pomodoro"],
    }));
    expect(screen.getByText("Manca: Acciughe, Basilico, Capperi e altri 2")).toBeVisible();
  });

  it("al singolare dice «un altro»", () => {
    renderRow(ricetta({
      missing: 4, cookable: false,
      missing_names: ["Acciughe", "Basilico", "Capperi", "Olive"],
    }));
    expect(screen.getByText("Manca: Acciughe, Basilico, Capperi e un altro")).toBeVisible();
  });

  it("senza nomi dice quanti ne mancano, mai «Manca:» e niente", () => {
    renderRow(ricetta({ missing: 2, cookable: false }));
    expect(screen.getByText("Mancano 2 ingredienti")).toBeVisible();
  });

  it("sotto, categoria, costo e minuti", () => {
    renderRow(ricetta({ category: "Primi piatti", cost: 4, prep_minutes: 10, cook_minutes: 15 }));
    expect(screen.getByText("Primi piatti")).toBeVisible();
    expect(screen.getByRole("img", { name: "Costo 4 su 5" })).toBeInTheDocument();
    expect(screen.getByText("25 min")).toBeVisible();
  });

  it("senza costo non mostra cinque € grigi", () => {
    renderRow(ricetta({ cost: null }));
    expect(screen.queryByRole("img", { name: /Costo/ })).not.toBeInTheDocument();
    expect(screen.queryByText("€")).not.toBeInTheDocument();
  });

  it("senza categoria, costo né minuti la riga di sotto non c'è", () => {
    const { container } = renderRow(ricetta());
    expect(container.textContent).not.toContain("·");
  });

  it("non dice più la provenienza, né la descrizione", () => {
    renderRow(ricetta({ source: "dataset", description: "Di sempre" }));
    expect(screen.queryByText("dataset")).toBeNull();
    expect(screen.queryByText("Di sempre")).toBeNull();
  });

  it("tutta la riga porta alla ricetta, e il suo nome comincia dal titolo", () => {
    renderRow(ricetta());
    expect(screen.getByRole("link", { name: /^Pasta al pomodoro/ })).toHaveAttribute(
      "href", "/ricette/r1"
    );
  });

  it("la miniatura riceve la foto e il reparto principale", () => {
    const { container } = renderRow(
      ricetta({ image_url: "https://esempio.invalid/p.jpg", main_department: "verdura" })
    );
    const mini = container.querySelector("[data-recipe-thumb]");
    expect(mini).toHaveAttribute("data-dept", "verdura");
    expect(mini?.querySelector("img")).toHaveAttribute("src", "https://esempio.invalid/p.jpg");
  });
});
