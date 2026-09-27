import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FillSlider } from "./FillSlider";

// jsdom non impagina niente: senza questo ogni riquadro è largo zero e nessuna
// posizione del dito vorrebbe dire un valore. La geometria è quella di un cursore
// largo 228px che parte da x=0: col pallino da 28px il centro corre da 14 a 214,
// cioè 2px per punto percentuale — il valore v sta a x = 14 + 2v.
function renderSlider(props: Partial<Parameters<typeof FillSlider>[0]> = {}) {
  const onCommit = vi.fn();
  const view = render(<FillSlider value={70} label="mela" onCommit={onCommit} {...props} />);
  const cursore = screen.getByRole("slider") as HTMLInputElement;
  vi.spyOn(cursore, "getBoundingClientRect").mockReturnValue({
    x: 0,
    y: 0,
    left: 0,
    top: 0,
    right: 228,
    bottom: 44,
    width: 228,
    height: 44,
    toJSON: () => ({}),
  });
  // il dito non tocca mai l'`<input>` (non riceve eventi del puntatore, vedi il
  // componente): li riceve il contenitore. Mandarli all'input li farebbe risalire
  // lo stesso, e il test passerebbe anche con i gestori nel posto sbagliato.
  const superficie = cursore.parentElement!;
  return { ...view, onCommit, cursore, superficie };
}

const at = (percent: number) => 14 + 2 * percent;

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FillSlider", () => {
  it("è un cursore da 0 a 100 e dice di cosa parla", () => {
    render(<FillSlider value={70} label="mela" onCommit={() => {}} />);
    const cursore = screen.getByRole("slider", { name: "Quanto ne resta di mela" });
    expect(cursore.getAttribute("min")).toBe("0");
    expect(cursore.getAttribute("max")).toBe("100");
    expect((cursore as HTMLInputElement).value).toBe("70");
  });

  it("un tocco — il dito si posa e si alza nello stesso punto — porta il cursore lì e scrive una volta", () => {
    const { onCommit, cursore, superficie } = renderSlider();

    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    expect(onCommit).not.toHaveBeenCalled();
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });

    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith(40);
    expect(cursore.value).toBe("40");
  });

  it("il tremolio di un dito che si alza è ancora un tocco, e conta dove si è posato", () => {
    const { onCommit, superficie } = renderSlider();

    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    fireEvent.pointerMove(superficie, { pointerId: 1, isPrimary: true, clientX: at(40) + 5, clientY: 25 });
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: at(40) + 5, clientY: 25 });

    expect(onCommit).toHaveBeenCalledWith(40);
  });

  it("uno scorrimento verticale che parte dal cursore non cambia niente e non scrive", () => {
    // il difetto S13: scorrendo la dispensa col dito posato su un cursore, il
    // valore si spostava e al sollevarsi del dito veniva scritto
    const { onCommit, cursore, superficie } = renderSlider();

    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    fireEvent.pointerMove(superficie, { pointerId: 1, isPrimary: true, clientX: at(42), clientY: 60 });
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: at(42), clientY: 60 });

    expect(onCommit).not.toHaveBeenCalled();
    expect(cursore.value).toBe("70");
  });

  it("anche un trascinamento orizzontale non cambia niente: si cambia solo toccando", () => {
    const { onCommit, cursore, superficie } = renderSlider();

    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: at(70), clientY: 22 });
    fireEvent.pointerMove(superficie, { pointerId: 1, isPrimary: true, clientX: at(30), clientY: 22 });
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: at(30), clientY: 22 });

    expect(onCommit).not.toHaveBeenCalled();
    expect(cursore.value).toBe("70");
  });

  it("tornare al punto di partenza dopo essersi allontanati non rende il gesto un tocco", () => {
    // la tolleranza si misura sul tragitto, non solo sul punto d'arrivo: un dito
    // che scorre la pagina e torna indietro prima di alzarsi ha trascinato
    const { onCommit, superficie } = renderSlider();

    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    fireEvent.pointerMove(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 80 });
    fireEvent.pointerMove(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });

    expect(onCommit).not.toHaveBeenCalled();
  });

  it("quando il browser si prende il gesto per scorrere, il sollevarsi del dito non scrive", () => {
    // `pointercancel` è ciò che manda il browser quando decide che il gesto è uno
    // scorrimento della pagina
    const { onCommit, superficie } = renderSlider();

    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    fireEvent.pointerCancel(superficie, { pointerId: 1 });
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });

    expect(onCommit).not.toHaveBeenCalled();
  });

  it("un tocco oltre le estremità vale l'estremità, e cade sul passo di 5", () => {
    const { onCommit, superficie } = renderSlider();

    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: 2, clientY: 22 });
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: 2, clientY: 22 });
    expect(onCommit).toHaveBeenLastCalledWith(0);

    // 14 + 2·43 = 100 → 43%, che col passo di 5 diventa 45
    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: 100, clientY: 22 });
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: 100, clientY: 22 });
    expect(onCommit).toHaveBeenLastCalledWith(45);
  });

  it("un secondo dito — lo zoom a due dita — annulla il tocco del primo", () => {
    const { onCommit, superficie } = renderSlider();
    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    fireEvent.pointerDown(superficie, { pointerId: 2, isPrimary: false, clientX: at(60), clientY: 22 });
    fireEvent.pointerUp(superficie, { pointerId: 2, isPrimary: false, clientX: at(60), clientY: 22 });
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("un tocco sulla posizione che ha già non manda niente", () => {
    const { onCommit, superficie } = renderSlider();
    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: at(70), clientY: 22 });
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: at(70), clientY: 22 });
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("un sollevarsi senza nessun appoggio prima non scrive", () => {
    // un dito posato fuori, trascinato sopra e alzato qui non è un tocco su questo
    // cursore
    const { onCommit, superficie } = renderSlider();
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("disabilitato, un tocco non fa niente", () => {
    const { onCommit, cursore, superficie } = renderSlider({ disabled: true });
    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    expect(onCommit).not.toHaveBeenCalled();
    expect(cursore.value).toBe("70");
  });

  it("il tasto destro del mouse non è un tocco", () => {
    const { onCommit, superficie } = renderSlider();
    fireEvent.pointerDown(superficie, {
      pointerId: 1,
      isPrimary: true,
      pointerType: "mouse",
      button: 2,
      clientX: at(40),
      clientY: 22,
    });
    fireEvent.pointerUp(superficie, {
      pointerId: 1,
      isPrimary: true,
      pointerType: "mouse",
      button: 2,
      clientX: at(40),
      clientY: 22,
    });
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("anche da tastiera si scrive, quando il tasto si alza", () => {
    const { onCommit, cursore } = renderSlider();
    fireEvent.change(cursore, { target: { value: "75" } });
    expect(onCommit).not.toHaveBeenCalled();
    fireEvent.keyUp(cursore, { key: "ArrowRight" });
    expect(onCommit).toHaveBeenCalledWith(75);
  });

  it("lasciato dov'era non manda niente", () => {
    const { onCommit, cursore } = renderSlider();
    fireEvent.keyUp(cursore, { key: "Tab" });
    fireEvent.blur(cursore);
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("una posizione arrivata dal server riprende il comando", () => {
    // l'annulla, una ricarica, una cottura: quando la verità cambia da fuori il
    // cursore non può restare dove l'ha lasciato la tastiera
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
    const { onCommit, cursore, superficie } = renderSlider();

    fireEvent.pointerDown(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    fireEvent.pointerUp(superficie, { pointerId: 1, isPrimary: true, clientX: at(40), clientY: 22 });
    expect(onCommit).toHaveBeenCalledTimes(1);

    // `value` è ancora 70 (il server non ha risposto): senza guardia sulla
    // posizione già inviata, questo blur rilancerebbe onCommit(40) una seconda
    // volta
    fireEvent.blur(cursore);
    expect(onCommit).toHaveBeenCalledTimes(1);
  });

  it("il blur da solo scrive, anche se il tasto non si è mai alzato", () => {
    // aggravante segnalata in revisione: cancellando `onBlur` dal componente i
    // test restavano tutti verdi. Questo fallisce se `onBlur` non c'è più.
    const { onCommit, cursore } = renderSlider();

    fireEvent.change(cursore, { target: { value: "40" } });
    fireEvent.blur(cursore);
    expect(onCommit).toHaveBeenCalledWith(40);
  });
});
