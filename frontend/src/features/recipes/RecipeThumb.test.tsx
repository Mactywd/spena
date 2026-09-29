import { describe, expect, it } from "vitest";
import { fireEvent, render } from "@testing-library/react";
import { RecipeThumb } from "./RecipeThumb";

// Le classi qui sono la mappa reparto → icona e tinta, non la disposizione: che la
// miniatura sia davvero 56 px e che la tinta si veda lo misura il browser
// (`frontend/e2e/style.spec.ts`, «la miniatura»).
function miniatura(container: HTMLElement): HTMLElement {
  return container.querySelector<HTMLElement>("[data-recipe-thumb]")!;
}

describe("RecipeThumb", () => {
  it("senza foto mostra l'icona del reparto principale sulla sua tinta", () => {
    const { container } = render(<RecipeThumb imageUrl={null} department="pesce" />);
    const mini = miniatura(container);
    expect(mini).toHaveClass("bg-dept-blue");
    expect(mini).toHaveAttribute("data-dept", "pesce");
    expect(mini.querySelector("svg.tabler-icon-fish")).not.toBeNull();
    expect(mini.querySelector("img")).toBeNull();
  });

  it("con la foto l'icona resta sotto: mentre carica non c'è un rettangolo bianco", () => {
    const { container } = render(
      <RecipeThumb imageUrl="https://esempio.invalid/p.jpg" department="verdura" />
    );
    const mini = miniatura(container);
    expect(mini).toHaveClass("bg-dept-peach");
    expect(mini.querySelector("svg.tabler-icon-carrot")).not.toBeNull();
    const foto = mini.querySelector("img")!;
    expect(foto).toHaveAttribute("src", "https://esempio.invalid/p.jpg");
    // decorativa: il titolo è già il nome del collegamento, l'alt lo ripeterebbe
    expect(foto).toHaveAttribute("alt", "");
    expect(foto).toHaveAttribute("loading", "lazy");
  });

  it("una foto che non carica lascia l'icona, non un buco", () => {
    const { container } = render(
      <RecipeThumb imageUrl="https://esempio.invalid/rotta.jpg" department="verdura" />
    );
    fireEvent.error(miniatura(container).querySelector("img")!);
    expect(miniatura(container).querySelector("img")).toBeNull();
    expect(miniatura(container).querySelector("svg.tabler-icon-carrot")).not.toBeNull();
  });

  it("senza reparto, l'icona del ricettario su ardesia", () => {
    const { container } = render(<RecipeThumb imageUrl={null} department={null} />);
    const mini = miniatura(container);
    expect(mini).toHaveClass("bg-dept-slate");
    expect(mini).toHaveAttribute("data-dept", "");
    expect(mini.querySelector("svg.tabler-icon-tools-kitchen-2")).not.toBeNull();
  });
});
