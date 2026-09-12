import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StatusToggle } from "./StatusToggle";
import { STATUS_LABELS, STATUS_TONE } from "./statusLabels";

describe("StatusToggle", () => {
  // Questo test esiste perché la mappa dei colori può essere giusta mentre il
  // controllo che la gente tocca non la usa: è il difetto che su questo ramo è
  // sopravvissuto tre volte (vedi CLAUDE.md). Si interroga il componente vero, non
  // una copia della mappa.
  it.each(["available", "low", "finished"] as const)(
    "veste la posizione scelta col colore di %s",
    (status) => {
      render(<StatusToggle value={status} onChange={() => {}} />);
      const chosen = screen.getByRole("button", { name: STATUS_LABELS[status], pressed: true });
      for (const token of STATUS_TONE[status].fill.split(" ")) {
        expect(chosen).toHaveClass(token);
      }
    }
  );

  it("lascia le posizioni non scelte senza il colore dello stato", () => {
    render(<StatusToggle value="available" onChange={() => {}} />);
    const other = screen.getByRole("button", { name: STATUS_LABELS.low, pressed: false });
    expect(other).not.toHaveClass(STATUS_TONE.low.fill.split(" ")[0]);
  });

  // il bersaglio da pollice è un requisito, non un dettaglio estetico: si tocca
  // camminando, con una mano, e una lista di bersagli piccoli si sbaglia
  it("tiene bersagli da pollice", () => {
    render(<StatusToggle value="available" onChange={() => {}} />);
    for (const label of Object.values(STATUS_LABELS)) {
      expect(screen.getByRole("button", { name: label })).toHaveClass("min-h-11");
    }
  });

  it("non chiama onChange quando è disabilitato", async () => {
    const onChange = vi.fn();
    render(<StatusToggle value="available" onChange={onChange} disabled />);
    await userEvent.click(screen.getByRole("button", { name: STATUS_LABELS.low }));
    expect(onChange).not.toHaveBeenCalled();
  });
});
