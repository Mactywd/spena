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

  it("un secondo evento sulla stessa posizione non manda una seconda PATCH mentre il server non ha ancora risposto", () => {
    // il difetto: la guardia confrontava `position` con `value` (la verità del
    // server), non con l'ultima posizione già inviata. Finché il refetch dopo la
    // prima PATCH non è arrivato, `value` resta quello vecchio — e un secondo
    // evento (un'altra riga toccata, un Tab) rilancia una scrittura che l'utente
    // non ha chiesto una seconda volta.
    const onCommit = vi.fn();
    render(<FillSlider value={70} label="mela" onCommit={onCommit} />);
    const cursore = screen.getByRole("slider");

    fireEvent.change(cursore, { target: { value: "40" } });
    fireEvent.pointerUp(cursore);
    expect(onCommit).toHaveBeenCalledTimes(1);

    // `value` è ancora 70 (il server non ha risposto): senza guardia sulla
    // posizione già inviata, questo blur rilancerebbe onCommit(40) una seconda
    // volta
    fireEvent.blur(cursore);
    expect(onCommit).toHaveBeenCalledTimes(1);
  });

  it("il blur da solo scrive, anche se il dito non si è mai alzato", () => {
    // aggravante segnalata in revisione: cancellando `onBlur` dal componente i
    // test restavano tutti verdi. Questo fallisce se `onBlur` non c'è più.
    const onCommit = vi.fn();
    render(<FillSlider value={70} label="mela" onCommit={onCommit} />);
    const cursore = screen.getByRole("slider");

    fireEvent.change(cursore, { target: { value: "40" } });
    fireEvent.blur(cursore);
    expect(onCommit).toHaveBeenCalledWith(40);
  });
});
