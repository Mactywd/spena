import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ServingsStepper } from "./ServingsStepper";

const MOTIVO = "Porzioni non indicate: si cambiano da «Modifica».";

describe("ServingsStepper", () => {
  it("con le porzioni, i due tasti cambiano il numero", async () => {
    const onChange = vi.fn();
    render(<ServingsStepper value={2} onChange={onChange} />);

    expect(screen.getByText("2")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Una porzione in più" }));
    await userEvent.click(screen.getByRole("button", { name: "Una porzione in meno" }));
    expect(onChange.mock.calls).toEqual([[3], [1]]);
  });

  it("ai bordi il tasto che uscirebbe dalla scala è spento", () => {
    const { rerender } = render(<ServingsStepper value={1} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Una porzione in meno" })).toBeDisabled();
    rerender(<ServingsStepper value={50} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Una porzione in più" })).toBeDisabled();
  });

  it("senza porzioni si vede lo stesso, e dice una volta sola perché non si usa", async () => {
    // dal giro di T3: lo stepper spariva senza dirlo, e non si capiva se mancasse
    // qualcosa o se la ricetta non si potesse riscalare
    const onChange = vi.fn();
    render(<ServingsStepper value={null} onChange={onChange} />);

    const piu = screen.getByRole("button", { name: "Una porzione in più" });
    expect(piu).toHaveAttribute("aria-disabled", "true");
    expect(piu).toHaveAccessibleDescription(MOTIVO);
    expect(screen.getAllByText(MOTIVO)).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Una porzione in meno" })).toBeDisabled();
    expect(screen.getByText("—")).toBeInTheDocument();

    await userEvent.click(piu);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("i due tasti sono di sola icona, col nome intero, e bersagli da pollice", () => {
    render(<ServingsStepper value={2} onChange={() => {}} />);
    for (const name of ["Una porzione in meno", "Una porzione in più"]) {
      const tasto = screen.getByRole("button", { name });
      expect(tasto.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
      expect(tasto.className).toContain("size-11");
    }
  });
});
