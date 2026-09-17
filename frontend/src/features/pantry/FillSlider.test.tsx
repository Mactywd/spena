import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FillSlider } from "./FillSlider";

describe("FillSlider", () => {
  it("è un cursore da 0 a 100 e dice di cosa parla", () => {
    render(<FillSlider value={70} label="mela" onCommit={() => {}} />);
    const cursore = screen.getByRole("slider", { name: "Quanto ne resta di mela" });
    expect(cursore.getAttribute("min")).toBe("0");
    expect(cursore.getAttribute("max")).toBe("100");
    expect((cursore as HTMLInputElement).value).toBe("70");
  });

  it("mentre il dito trascina non manda niente: scrive quando lo si lascia", () => {
    // una PATCH per ogni pixel di trascinamento sarebbe una richiesta ogni pochi
    // millisecondi, e l'ultima a rispondere vincerebbe
    const onCommit = vi.fn();
    render(<FillSlider value={70} label="mela" onCommit={onCommit} />);
    const cursore = screen.getByRole("slider");

    fireEvent.change(cursore, { target: { value: "40" } });
    expect(onCommit).not.toHaveBeenCalled();

    fireEvent.pointerUp(cursore);
    expect(onCommit).toHaveBeenCalledWith(40);
  });

  it("lasciato dov'era non manda niente", () => {
    const onCommit = vi.fn();
    render(<FillSlider value={70} label="mela" onCommit={onCommit} />);
    fireEvent.pointerUp(screen.getByRole("slider"));
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("anche da tastiera si scrive, quando il tasto si alza", () => {
    const onCommit = vi.fn();
    render(<FillSlider value={70} label="mela" onCommit={onCommit} />);
    const cursore = screen.getByRole("slider");
    fireEvent.change(cursore, { target: { value: "75" } });
    fireEvent.keyUp(cursore, { key: "ArrowRight" });
    expect(onCommit).toHaveBeenCalledWith(75);
  });

  it("una posizione arrivata dal server riprende il comando", () => {
    // l'annulla, una ricarica, una cottura: quando la verità cambia da fuori il
    // cursore non può restare dove l'ha lasciato il dito
    const { rerender } = render(<FillSlider value={70} label="mela" onCommit={() => {}} />);
    fireEvent.change(screen.getByRole("slider"), { target: { value: "10" } });
    rerender(<FillSlider value={0} label="mela" onCommit={() => {}} />);
    expect((screen.getByRole("slider") as HTMLInputElement).value).toBe("0");
  });
});
