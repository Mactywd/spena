import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type ComponentProps } from "react";
import { StockingRow } from "./StockingRow";
import type { Product, ShoppingItem } from "../../domain/types";

const MELE: ShoppingItem = {
  id: "s2", raw_text: "mele", ingredient_id: "i2", ingredient_name: "mela",
  ingredient_category: "frutta", ingredient_kind: "food", status: "checked", reason: "manual",
  created_at: "2026-09-29T10:00:00Z",
};
const STRANA: ShoppingItem = {
  ...MELE, id: "s3", raw_text: "cosa strana", ingredient_id: null, ingredient_name: null,
  ingredient_category: null, ingredient_kind: null,
};
const FAGE: Product = {
  id: "p1", ingredient_id: "i2", ingredient_name: "mela", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};

type Props = ComponentProps<typeof StockingRow>;

function baseProps(): Props {
  return {
    item: MELE, resolution: undefined, ingredientId: "i2", expiry: undefined, onExpiry: vi.fn(),
    matchNotSaved: false, retryingMatch: false, onRetryMatch: vi.fn(), focused: false,
    returnFocusTo: null, onFocusReturned: vi.fn(), onOpen: vi.fn(), onLoose: vi.fn(),
    onChange: vi.fn(),
  };
}

function renderRow(over: Partial<Props> = {}) {
  const props = { ...baseProps(), ...over };
  render(
    <ul>
      <StockingRow {...props} />
    </ul>
  );
  return props;
}

/** La scadenza tenuta da un genitore vero, come la tiene lo schermo. */
function ExpiryHarness() {
  const [expiry, setExpiry] = useState<string | undefined>(undefined);
  return (
    <ul>
      <StockingRow {...baseProps()} expiry={expiry} onExpiry={setExpiry} />
    </ul>
  );
}

describe("StockingRow", () => {
  it("una voce da scegliere ha le tre icone in un gruppo con un nome, e ognuna fa la sua", async () => {
    const { onOpen, onLoose } = renderRow();
    const toolbar = screen.getByRole("toolbar", { name: "Come entra in dispensa: mele" });
    const [codice, catalogo, sfuso] = within(toolbar).getAllByRole("button");
    expect(codice).toHaveAccessibleName("Codice a barre per mele");
    expect(catalogo).toHaveAccessibleName("Cerca a catalogo per mele");
    expect(sfuso).toHaveAccessibleName("Sfuso, senza marca: mele");
    await userEvent.click(codice);
    await userEvent.click(catalogo);
    await userEvent.click(sfuso);
    expect(vi.mocked(onOpen).mock.calls).toEqual([["scanner"], ["catalog"]]);
    expect(onLoose).toHaveBeenCalledTimes(1);
  });

  it("risolta sfusa dice «Sfuso» sotto il nome, e «Cambia» è un'icona", async () => {
    const { onChange } = renderRow({ resolution: { kind: "loose" } });
    expect(screen.getByText("Sfuso")).toBeDefined();
    expect(screen.queryByRole("toolbar")).toBeNull();
    const cambia = screen.getByRole("button", { name: "Cambia la scelta per mele" });
    expect(cambia.textContent).toBe("");
    await userEvent.click(cambia);
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("risolta con un prodotto dice quale, con la marca", () => {
    renderRow({ resolution: { kind: "product", product: FAGE } });
    expect(screen.getByText("Total 0%").parentElement).toHaveTextContent("Total 0% · Fage");
  });

  it("una voce senza ingrediente è chiusa: solo «Abbina»", async () => {
    const { onOpen } = renderRow({ item: STRANA, ingredientId: null });
    expect(screen.queryByRole("toolbar")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Abbina: cosa strana" }));
    expect(onOpen).toHaveBeenCalledWith("match");
  });

  it("«+ scadenza» apre il campo", async () => {
    const { onExpiry } = renderRow();
    expect(screen.queryByLabelText(/Scadenza di mele/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "+ scadenza per mele" }));
    expect(onExpiry).toHaveBeenCalledWith("");
  });

  it("il campo ha un'etichetta che si vede, e la ✕ lo chiude svuotandolo", async () => {
    const { onExpiry } = renderRow({ expiry: "2026-10-02" });
    const field = screen.getByLabelText(/Scadenza di mele/) as HTMLInputElement;
    expect(field).toHaveValue("2026-10-02");
    expect(field.labels![0]).not.toHaveClass("sr-only");
    await userEvent.click(screen.getByRole("button", { name: "Togli la data di scadenza per mele" }));
    expect(onExpiry).toHaveBeenCalledWith(undefined);
  });

  it("l'Invio nel campo non preme niente; Esc lo chiude svuotandolo", () => {
    const { onExpiry } = renderRow({ expiry: "2026-10-02" });
    const field = screen.getByLabelText(/Scadenza di mele/);
    // senza `preventDefault` l'Invio arrivava al pulsante che riprendeva il fuoco (Consegna 1)
    expect(fireEvent.keyDown(field, { key: "Enter" })).toBe(false);
    expect(onExpiry).not.toHaveBeenCalled();
    fireEvent.keyDown(field, { key: "Escape" });
    expect(onExpiry).toHaveBeenCalledWith(undefined);
  });

  it("chiuso il campo con la ✕, il fuoco torna a «+ scadenza»", async () => {
    render(<ExpiryHarness />);
    await userEvent.click(screen.getByRole("button", { name: "+ scadenza per mele" }));
    const field = screen.getByLabelText(/Scadenza di mele/);
    expect(document.activeElement).toBe(field);
    await userEvent.click(screen.getByRole("button", { name: "Togli la data di scadenza per mele" }));
    expect(screen.queryByLabelText(/Scadenza di mele/)).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "+ scadenza per mele" }));
  });

  it("il fuoco torna al pulsante che aveva aperto il pannello", () => {
    const { onFocusReturned } = renderRow({ returnFocusTo: "catalog" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Cerca a catalogo per mele" }));
    expect(onFocusReturned).toHaveBeenCalled();
  });

  it("non toglie il fuoco a chi è già altrove: lo rimette solo se è caduto sulla pagina", () => {
    // la richiesta dopo un abbinamento arriva con la rilettura, anche un momento dopo
    const outside = document.createElement("input");
    document.body.appendChild(outside);
    outside.focus();
    const { onFocusReturned } = renderRow({ returnFocusTo: "catalog" });
    expect(document.activeElement).toBe(outside);
    // la richiesta è consumata lo stesso: non resta in attesa di rubarlo più tardi
    expect(onFocusReturned).toHaveBeenCalled();
    outside.remove();
  });

  it("a voce risolta il fuoco va a «Cambia»", () => {
    renderRow({ resolution: { kind: "loose" }, returnFocusTo: "change" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Cambia la scelta per mele" }));
  });

  it("col pannello aperto la voce viene in cima (S10)", () => {
    const targets: Element[] = [];
    const spy = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(function (this: Element) {
        targets.push(this);
      });
    renderRow({ focused: true });
    expect(targets).toEqual([screen.getByText("mele").closest("li")]);
    spy.mockRestore();
  });

  it("il pannello sta dentro la voce, sotto la sua riga", () => {
    renderRow({ children: <p>il pannello</p> });
    const name = screen.getByText("mele");
    const panel = screen.getByText("il pannello");
    expect(panel.closest("li")).toBe(name.closest("li"));
    expect(name.compareDocumentPosition(panel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("l'abbinamento non ricordato lo dice accanto, con «Riprova» (S19)", async () => {
    const { onRetryMatch } = renderRow({ item: STRANA, ingredientId: "i9", matchNotSaved: true });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Non sono riuscito a ricordare l'abbinamento in lista"
    );
    await userEvent.click(screen.getByRole("button", { name: "Riprova ad abbinare cosa strana" }));
    expect(onRetryMatch).toHaveBeenCalledTimes(1);
  });

  it("mentre riprova, «Riprova» si spegne ma tiene il fuoco, e non riparte", async () => {
    const { onRetryMatch } = renderRow({
      item: STRANA, ingredientId: "i9", matchNotSaved: true, retryingMatch: true,
    });
    const retry = screen.getByRole("button", { name: "Riprova ad abbinare cosa strana" });
    expect(retry).toHaveAttribute("aria-disabled", "true");
    expect(retry).not.toBeDisabled();
    await userEvent.click(retry);
    expect(onRetryMatch).not.toHaveBeenCalled();
  });
});
