import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { IngredientFigure } from "./IngredientFigure";

function figura(container: HTMLElement): HTMLElement {
  return container.querySelector("[data-figure]") as HTMLElement;
}

describe("IngredientFigure (S12)", () => {
  it("con un'emoji mostra l'emoji, ed è nascosta a chi ascolta", () => {
    const { container } = render(<IngredientFigure emoji="🥕" category="verdura" />);
    const el = figura(container);
    expect(el.dataset.figure).toBe("emoji");
    expect(el.textContent).toBe("🥕");
    // senza, uno screen reader leggerebbe «carota Carota» (bozza §3.A)
    expect(el.getAttribute("aria-hidden")).toBe("true");
    expect(el.querySelector("svg")).toBeNull();
  });

  it("senza emoji mostra l'icona del reparto, in grigio e senza la tinta del reparto", () => {
    const { container } = render(<IngredientFigure emoji={null} category="latticini" />);
    const el = figura(container);
    expect(el.dataset.figure).toBe("reparto");
    expect(el.querySelector("svg.tabler-icon-cheese")).not.toBeNull();
    expect(el.className).toContain("text-ink-faint");
    expect(el.className).toContain("bg-page");
    // le tinte dei reparti stanno solo nel titolo della sezione (spec T3 §3.3)
    expect(el.className).not.toMatch(/dept-/);
  });

  it("una risposta senza il campo vale come nessuna emoji", () => {
    const { container } = render(<IngredientFigure emoji={undefined} category="verdura" />);
    expect(figura(container).dataset.figure).toBe("reparto");
    expect(figura(container).querySelector("svg.tabler-icon-carrot")).not.toBeNull();
  });

  it("un reparto sconosciuto ripiega sulla scatola, come i titoli delle sezioni", () => {
    const { container } = render(<IngredientFigure emoji={null} category="inventato" />);
    expect(figura(container).querySelector("svg.tabler-icon-package")).not.toBeNull();
  });
});
