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

  // jsdom non calcola il CSS, quindi qui si legge l'elenco delle classi e non il raggio
  // a video. Due utilità di raggio sullo stesso elemento non le decide l'ordine in cui
  // sono scritte ma quello del CSS compilato: la prima stesura aggiungeva
  // `rounded-[10px]` a un `rounded-full`, e vinceva il cerchio. Il raggio vero lo misura
  // il browser in `style.spec.ts`.
  it("il + è un quadrato dagli angoli morbidi, con un raggio solo", () => {
    render(<Harness onAdd={() => {}} />);
    const radii = screen
      .getByRole("button", { name: "Aggiungi in dispensa" })
      .className.split(/\s+/)
      .filter((c) => c.startsWith("rounded"));
    expect(radii).toEqual(["rounded-[10px]"]);
  });
});
