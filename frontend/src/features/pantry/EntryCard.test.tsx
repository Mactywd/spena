import { type ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EntryCard } from "./EntryCard";
import type { EntryChoice } from "./entryView";
import type { Product } from "../../domain/types";

const YOGURT = { id: "i1", name: "yogurt greco", kind: "food" } as const;
const FAGE: Product = {
  id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};

type Props = ComponentProps<typeof EntryCard>;

function renderCard(over: Partial<Props> = {}) {
  const props: Props = {
    choice: { ingredient: YOGURT, product: FAGE }, expiry: undefined, onExpiry: vi.fn(),
    busy: false, failed: false, justEntered: false, onChange: vi.fn(), onConfirm: vi.fn(),
    onCancel: vi.fn(), ...over,
  };
  const view = render(<EntryCard {...props} />);
  return { ...props, ...view };
}

const CASES: [string, EntryChoice, string, string][] = [
  ["un prodotto", { ingredient: YOGURT, product: FAGE }, "Total 0%", "Fage · yogurt greco"],
  ["uno sfuso", { ingredient: YOGURT, product: null }, "Yogurt greco", "Sfuso, senza marca · yogurt greco"],
];

describe("EntryCard", () => {
  it.each(CASES)("dice cosa entra: %s", (_caso, choice, title, detail) => {
    renderCard({ choice });
    expect(screen.getByText(title)).toBeDefined();
    expect(screen.getByText(detail)).toBeDefined();
  });

  it("«Metti in dispensa» ha il fuoco appena la scheda compare, e i tre pulsanti fanno la loro", async () => {
    const { onConfirm, onChange, onCancel } = renderCard();
    const metti = screen.getByRole("button", { name: "Metti in dispensa" });
    expect(document.activeElement).toBe(metti);
    await userEvent.click(metti);
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Cambia: Total 0%" }));
    expect(onChange).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("le strade del codice e del catalogo ci sono solo se la scheda le offre", async () => {
    const sfuso: EntryChoice = { ingredient: YOGURT, product: null };
    const { unmount } = renderCard({ choice: sfuso });
    expect(screen.queryByRole("toolbar")).toBeNull();
    unmount();

    const onCode = vi.fn();
    const onCatalog = vi.fn();
    renderCard({ choice: sfuso, onCode, onCatalog });
    expect(screen.getByText("Con la marca:")).toBeDefined();
    const toolbar = screen.getByRole("toolbar", { name: "Con la marca: Yogurt greco" });
    await userEvent.click(within(toolbar).getByRole("button", { name: "Codice a barre per Yogurt greco" }));
    await userEvent.click(within(toolbar).getByRole("button", { name: "Cerca a catalogo per Yogurt greco" }));
    expect(onCode).toHaveBeenCalledTimes(1);
    expect(onCatalog).toHaveBeenCalledTimes(1);
  });

  it("la nota della serie, l'errore, e «Metti in dispensa» in volo", () => {
    renderCard({ justEntered: true, failed: true, busy: true });
    expect(
      screen.getByText("L'hai appena messo in dispensa: se è un'altra confezione, mettila pure.")
    ).toBeDefined();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Non sono riuscito ad aggiungere la voce in dispensa. Riprova."
    );
    expect(screen.getByRole("button", { name: "Metti in dispensa" })).toHaveAttribute(
      "aria-disabled",
      "true"
    );
  });
});
