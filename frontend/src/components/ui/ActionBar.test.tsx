import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ActionBar } from "./ActionBar";

function Harness({ onAdd }: { onAdd: (text: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <ActionBar
      inputLabel="Cerca o aggiungi in dispensa"
      placeholder="Cerca o aggiungi"
      addLabel="Aggiungi in dispensa"
      value={value}
      onChange={setValue}
      onAdd={onAdd}
    />
  );
}

describe("ActionBar", () => {
  it("il + e l'Invio aggiungono il testo scritto, senza spazi attorno", () => {
    const onAdd = vi.fn();
    render(<Harness onAdd={onAdd} />);
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "  latte " } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    expect(onAdd).toHaveBeenCalledWith("latte");
  });

  it("a campo vuoto il + non manda niente", () => {
    const onAdd = vi.fn();
    render(<Harness onAdd={onAdd} />);
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    expect(onAdd).not.toHaveBeenCalled();
  });

  it("il campo resta a 16px: sotto, iOS ingrandisce la pagina", () => {
    render(<Harness onAdd={() => {}} />);
    expect(screen.getByLabelText("Cerca o aggiungi in dispensa").className).toContain("text-base");
  });
});
