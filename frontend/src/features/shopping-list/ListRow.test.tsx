import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ListRow } from "./ListRow";
import type { ShoppingItem } from "../../domain/types";

const BASE: ShoppingItem = {
  id: "s1", raw_text: "Total 0%", ingredient_id: "i2", ingredient_name: "yogurt greco",
  ingredient_category: "latticini", ingredient_kind: "food", status: "pending",
  reason: "manual", created_at: "2026-09-28T10:00:00Z",
};

function renderRow(over: Partial<ShoppingItem> = {}, props: { busy?: boolean; failed?: boolean } = {}) {
  const onToggle = vi.fn();
  const onRemove = vi.fn();
  render(
    <ul>
      <ListRow item={{ ...BASE, ...over }} busy={props.busy ?? false} failed={props.failed ?? false}
        onToggle={onToggle} onRemove={onRemove} />
    </ul>
  );
  return { onToggle, onRemove };
}

describe("ListRow", () => {
  it("si legge il testo scritto, e la casella porta il nome dell'ingrediente abbinato", () => {
    renderRow();
    expect(screen.getByText("Total 0%")).toBeDefined();
    expect(screen.getByRole("checkbox", { name: "yogurt greco" })).toBeDefined();
  });

  it("una voce non abbinata porta il testo scritto anche sulla casella", () => {
    renderRow({ ingredient_id: null, ingredient_name: null, raw_text: "cosa verde" });
    expect(screen.getByRole("checkbox", { name: "cosa verde" })).toBeDefined();
  });

  it("toccando il nome la voce si spunta, non solo sulla casella (S17)", () => {
    const { onToggle } = renderRow();
    fireEvent.click(screen.getByText("Total 0%"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("la nota del rientro si legge, e fa parte del bersaglio che spunta", () => {
    const { onToggle } = renderRow({ reason: "finished_while_cooking" });
    fireEvent.click(screen.getByText("rientrata perché finita cucinando"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("la ✕ sta fuori dal bersaglio della spunta: togliere non spunta", () => {
    const { onToggle, onRemove } = renderRow();
    const remove = screen.getByRole("button", { name: "Togli Total 0% dalla lista" });
    expect(remove.closest("label")).toBeNull();
    fireEvent.click(remove);
    expect(onRemove).toHaveBeenCalledTimes(1);
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("una voce nel carrello è spuntata e barrata", () => {
    renderRow({ status: "checked" });
    expect(screen.getByRole("checkbox", { name: "yogurt greco" })).toBeChecked();
    expect(screen.getByText("Total 0%").className).toContain("line-through");
  });

  it("mentre una scrittura è in volo la casella è spenta ma tiene il fuoco", () => {
    const { onToggle, onRemove } = renderRow({}, { busy: true });
    const box = screen.getByRole("checkbox", { name: "yogurt greco" });
    // `aria-disabled` e non `disabled`: un controllo che diventa `disabled` perde il
    // fuoco, e chi spunta con la tastiera lo ritroverebbe sul `body`
    expect(box.hasAttribute("disabled")).toBe(false);
    expect(box).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(box);
    expect(onToggle).not.toHaveBeenCalled();
    expect(box).not.toBeChecked();
    const remove = screen.getByRole("button", { name: "Togli Total 0% dalla lista" });
    expect(remove.hasAttribute("disabled")).toBe(false);
    expect(remove).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(remove);
    expect(onRemove).not.toHaveBeenCalled();
  });

  it("in volo anche la ✕ resta raggiungibile dal fuoco (T3 Consegna 2)", () => {
    // con `disabled` il browser toglieva il fuoco alla ✕ appena partiva la PATCH, e dopo
    // una ✕ fallita chi usa la tastiera lo ritrovava sulla pagina
    renderRow({}, { busy: true });
    const remove = screen.getByRole("button", { name: "Togli Total 0% dalla lista" });
    remove.focus();
    expect(remove).toHaveFocus();
  });

  it("una scrittura fallita lo dice nella riga", () => {
    renderRow({}, { failed: true });
    expect(screen.getByRole("alert").textContent).toContain("riprova");
  });
});
