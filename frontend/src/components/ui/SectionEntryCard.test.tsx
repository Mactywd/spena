import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SectionEntryCard } from "./SectionEntryCard";

function renderCard(pending: boolean, note: string) {
  return render(
    <MemoryRouter>
      <SectionEntryCard to="/sistema" title="Sistema la spesa" note={note} pending={pending} />
    </MemoryRouter>
  );
}

describe("SectionEntryCard", () => {
  it("resta un collegamento anche quando non c'è niente da fare", () => {
    // è il punto della voce: una sottosezione che sparisce quando è vuota non si
    // può visitare apposta
    renderCard(false, "Niente di spuntato, per ora");
    const link = screen.getByRole("link", { name: /Sistema la spesa/ });
    expect(link.getAttribute("href")).toBe("/sistema");
    expect(screen.getByText("Niente di spuntato, per ora")).toBeDefined();
  });

  it("quando c'è da fare prende il fondo ambra e il pallino", () => {
    const { container } = renderCard(true, "3 voci spuntate da mettere via");
    expect(screen.getByRole("link", { name: /Sistema la spesa/ })).toHaveClass("bg-low-tint");
    // il pallino è decorazione: il messaggio lo porta la nota, che si legge
    expect(container.querySelector(".bg-low")).not.toBeNull();
  });

  it("senza da fare non c'è né pallino né ambra", () => {
    const { container } = renderCard(false, "Niente di spuntato, per ora");
    expect(screen.getByRole("link", { name: /Sistema la spesa/ })).not.toHaveClass("bg-low-tint");
    expect(container.querySelector(".bg-low")).toBeNull();
  });
});
