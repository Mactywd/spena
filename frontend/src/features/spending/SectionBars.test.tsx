import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { SectionBars } from "./SectionBars";
import type { SectionSpend } from "./types";

const SEZIONI: SectionSpend[] = [
  { call_site: "recipe_draft", label: "Ricette scritte con l'AI", cost_usd: 0.02, share: 0.8, calls: 3 },
  {
    call_site: "term_decision",
    label: "Abbinare gli ingredienti dell'import",
    cost_usd: 0.004,
    share: 0.16,
    calls: 1,
  },
  // una sezione che il server non conosce arriva col suo nome grezzo, e una spesa minuscola
  { call_site: "sezione_nuova", label: "sezione_nuova", cost_usd: 0.00004, share: 0.0016, calls: 1 },
  // solo chiamate senza costo
  { call_site: "unit_forms", label: "Forme delle unità", cost_usd: 0, share: 0, calls: 2 },
];

const leggibile = (testo: string | null) => (testo ?? "").replace(/\u00a0/g, " ");

describe("SectionBars", () => {
  it("una riga per sezione, nell'ordine del server, col nome, il costo e la quota", () => {
    render(<SectionBars sections={SEZIONI} />);

    const righe = within(screen.getByRole("list", { name: "Spesa per sezione" })).getAllByRole("listitem");
    expect(righe.map((riga) => leggibile(riga.textContent))).toEqual([
      "Ricette scritte con l'AI0,02 $ · 80%",
      "Abbinare gli ingredienti dell'import0,004 $ · 16%",
      "sezione_nuova< 0,0001 $ · < 1%",
      "Forme delle unità0,00 $ · 0%",
    ]);
  });

  it("la barra è lunga quanto la quota, una quota minuscola si vede, una nulla non c'è", () => {
    const { container } = render(<SectionBars sections={SEZIONI} />);

    const barre = Array.from(container.querySelectorAll("rect[data-bar]"));
    expect(barre.map((barra) => Number(barra.getAttribute("width")))).toEqual([80, 16, 1]);
    for (const barra of barre) expect(barra).toHaveClass("fill-brand");
  });

  it("ogni riga ha la sua traccia, e il disegno non si legge due volte", () => {
    const { container } = render(<SectionBars sections={SEZIONI} />);

    const disegni = Array.from(container.querySelectorAll("svg"));
    expect(disegni).toHaveLength(4);
    for (const disegno of disegni) {
      expect(disegno).toHaveAttribute("aria-hidden", "true");
      expect(disegno.querySelector("rect.fill-brand-tint")).not.toBeNull();
    }
  });
});
