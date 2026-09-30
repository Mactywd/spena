import { describe, expect, it, vi } from "vitest";
import { createRef } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";
import { buttonClasses, type ButtonShape, type ButtonVariant } from "./buttonClasses";
import { IconToolbar } from "./IconToolbar";
import { IconEye, IconLink, IconPencil, IconTrash } from "./icons";

describe("Button", () => {
  it("con il testo, il nome è il testo e l'icona non si legge", () => {
    render(<Button icon={IconPencil}>Modifica</Button>);
    const button = screen.getByRole("button", { name: "Modifica" });
    expect(button.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("di sola icona, il nome è l'etichetta completa", () => {
    const onClick = vi.fn();
    render(<Button icon={IconTrash} label="Elimina la ricetta" onClick={onClick} />);
    fireEvent.click(screen.getByRole("button", { name: "Elimina la ricetta" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("di sola icona è un quadrato da pollice", () => {
    render(<Button icon={IconTrash} label="Elimina" />);
    expect(screen.getByRole("button", { name: "Elimina" }).className).toContain("size-11");
  });

  it("è type=button se non si dice altro: dentro un modulo non deve inviarlo", () => {
    render(<Button>Annulla</Button>);
    expect(screen.getByRole("button", { name: "Annulla" })).toHaveAttribute("type", "button");
  });

  it("il `ref` arriva al pulsante vero: chi deve ridargli il fuoco lo trova", () => {
    const ref = createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Cucina</Button>);
    expect(ref.current).toBe(screen.getByRole("button", { name: "Cucina" }));
  });

  it("chi apre un pannello dice se è aperto e quale apre", () => {
    // i «Filtri» del ricettario (T3 Consegna 4): il pannello è in linea, sotto la barra
    render(<Button aria-expanded={false} aria-controls="pannello">Filtri</Button>);
    const button = screen.getByRole("button", { name: "Filtri" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveAttribute("aria-controls", "pannello");
  });

  // La guardia di TypeScript che il vincolo globale chiede: un pulsante di sola
  // icona senza `label` non deve compilare, perché per uno screen reader non ha
  // nome. Se la riga del `@ts-expect-error` smette di dare errore, la regola si è
  // rotta, e `npm run typecheck` lo dice.
  it("compila solo se l'unione icona+etichetta è rispettata (vedi il @ts-expect-error qui dentro)", () => {
    // @ts-expect-error icona sola senza `label` non deve compilare
    render(<Button icon={IconTrash} />);
  });

  // `busy` (T3 Consegna 2, «Restano aperti»): una richiesta partita da qui è in volo. Il
  // browser toglie il fuoco a un pulsante che diventa `disabled`, e chi usa la tastiera
  // lo ritrovava sul `body` dopo una ✕ fallita. jsdom non toglie il fuoco a un pulsante
  // che si spegne, ma rifiuta di darlo a uno già `disabled`: è questo che i test sotto
  // misurano. Il fuoco perso vero lo misura l'e2e (`style.spec.ts`).
  it("in volo è spento con aria-disabled, non con disabled, e un tocco non fa niente", () => {
    const onClick = vi.fn();
    render(<Button icon={IconTrash} label="Elimina" onClick={onClick} busy />);
    const button = screen.getByRole("button", { name: "Elimina" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button.hasAttribute("disabled")).toBe(false);
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("in volo resta raggiungibile dal fuoco", () => {
    render(<Button busy>Riprova</Button>);
    const button = screen.getByRole("button", { name: "Riprova" });
    button.focus();
    expect(button).toHaveFocus();
  });

  it("finito il volo torna a rispondere, e il fuoco non si è mosso", () => {
    const onClick = vi.fn();
    const { rerender } = render(<Button onClick={onClick} busy>Riprova</Button>);
    const button = screen.getByRole("button", { name: "Riprova" });
    button.focus();
    rerender(<Button onClick={onClick}>Riprova</Button>);
    expect(button).toHaveFocus();
    expect(button).not.toHaveAttribute("aria-disabled");
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("un submit in volo non invia il modulo", () => {
    const onSubmit = vi.fn((event: { preventDefault: () => void }) => event.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <Button type="submit" busy>
          Salva
        </Button>
      </form>
    );
    fireEvent.click(screen.getByRole("button", { name: "Salva" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("disabled resta, per un'azione che adesso non si può proprio fare", () => {
    render(<Button disabled>Salva</Button>);
    expect(screen.getByRole("button", { name: "Salva" })).toBeDisabled();
  });

  // `unavailableReason` (T3 Consegna 6a, la regola di Mattia): in volo → `busy`; «non si
  // può ancora» → `unavailableReason`, col perché; `disabled` solo dove nessuno dei due
  // vale. Il perché lo scrive `Button` sotto di sé, e lo lega al pulsante: prima ogni
  // chiamante lo scriveva a mano, e si scollava.
  it("«non ancora» è spento con aria-disabled, dice perché sotto e nella descrizione, e un tocco non fa niente", () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} unavailableReason="Scrivi il nome per crearlo.">
        Crea
      </Button>
    );
    const button = screen.getByRole("button", { name: "Crea" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button.hasAttribute("disabled")).toBe(false);
    expect(button).toHaveAccessibleDescription("Scrivi il nome per crearlo.");
    const reason = screen.getByText("Scrivi il nome per crearlo.");
    // sotto il pulsante, non dentro: il nome resta «Crea»
    expect(reason.tagName).toBe("P");
    expect(button.compareDocumentPosition(reason) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(reason.className.split(/\s+/)).toContain("text-ink-faint");
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("«non ancora» resta raggiungibile dal fuoco, e diventato pronto è lo stesso pulsante", () => {
    const onClick = vi.fn();
    const { rerender } = render(
      <Button onClick={onClick} unavailableReason="Manca il nome.">
        Salva
      </Button>
    );
    const button = screen.getByRole("button", { name: "Salva" });
    button.focus();
    expect(button).toHaveFocus();
    rerender(<Button onClick={onClick}>Salva</Button>);
    // lo stesso elemento, col fuoco: un `<button>` rinato lo avrebbe perso
    expect(screen.getByRole("button", { name: "Salva" })).toBe(button);
    expect(button).toHaveFocus();
    expect(button).not.toHaveAttribute("aria-disabled");
    expect(button).not.toHaveAttribute("aria-describedby");
    expect(screen.queryByText("Manca il nome.")).toBeNull();
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("il perché si aggiunge alla descrizione del chiamante, non la sostituisce", () => {
    render(
      <>
        <p id="nota-di-prova">Serve la rete.</p>
        <Button aria-describedby="nota-di-prova" unavailableReason="Manca il nome.">
          Salva
        </Button>
      </>
    );
    expect(screen.getByRole("button", { name: "Salva" })).toHaveAccessibleDescription(
      "Serve la rete. Manca il nome."
    );
  });

  it("un submit «non ancora» non invia il modulo, né col tocco né con l'Invio nel campo", async () => {
    const onSubmit = vi.fn((event: { preventDefault: () => void }) => event.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <label>
          Nome
          <input />
        </label>
        <Button type="submit" unavailableReason="Scrivi il nome per salvarlo.">
          Salva
        </Button>
      </form>
    );
    // l'Invio in un campo arriva al submit come un clic sul pulsante (l'invio implicito
    // del browser): è quel clic che `Button` rifiuta
    await userEvent.type(screen.getByLabelText("Nome"), "{Enter}");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("un motivo vuoto non è un motivo: il pulsante risponde, e sotto non c'è niente", () => {
    const onClick = vi.fn();
    const { container } = render(
      <Button onClick={onClick} unavailableReason="">
        Salva
      </Button>
    );
    const button = screen.getByRole("button", { name: "Salva" });
    expect(button).not.toHaveAttribute("aria-disabled");
    expect(container.querySelector("p")).toBeNull();
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("spento, il clic risale comunque agli antenati: si ignora solo dentro Button (vedi il JSDoc)", () => {
    // un `disabled` non manderebbe nessun clic; `aria-disabled` sì, e il gestore di un
    // antenato lo riceve. Nessun chiamante di oggi ne dipende: il test fissa quel che
    // il JSDoc promette, così chi lo cambia lo cambia apposta
    const onParent = vi.fn();
    const onClick = vi.fn();
    render(
      <div onClick={onParent}>
        <Button onClick={onClick} busy>
          In volo
        </Button>
        <Button onClick={onClick} unavailableReason="Non ancora.">
          Non ancora
        </Button>
      </div>
    );
    fireEvent.click(screen.getByRole("button", { name: "In volo" }));
    fireEvent.click(screen.getByRole("button", { name: "Non ancora" }));
    expect(onClick).not.toHaveBeenCalled();
    expect(onParent).toHaveBeenCalledTimes(2);
  });

  // `accessibleName` (Consegna 6a): un pulsante con testo che deve dire di più di quel
  // che mostra. «Abbina» e «Riprova» in «Sistema la spesa» ricodificavano il markup di
  // Button per riuscirci (idea di `next-steps.md`).
  it("con accessibleName il nome è quello, e il testo che si vede ne è l'inizio", () => {
    render(
      <Button icon={IconLink} accessibleName="Abbina: cosa strana">
        Abbina
      </Button>
    );
    const button = screen.getByRole("button", { name: "Abbina: cosa strana" });
    expect(button.textContent).toBe("Abbina");
    // label-in-name (WCAG 2.5.3): chi comanda a voce dice quel che vede
    expect("Abbina: cosa strana".startsWith(button.textContent!)).toBe(true);
  });

  it("accessibleName non compila su un pulsante di sola icona (vedi il @ts-expect-error qui dentro)", () => {
    // la forma di sola icona ha già `label`: due nomi per lo stesso pulsante sarebbero
    // un modo di sbagliarne uno
    // @ts-expect-error `accessibleName` è solo della forma con testo
    render(<Button icon={IconTrash} label="Elimina" accessibleName="Elimina tutto" />);
  });

  it("passa aria-pressed e aria-expanded, per un interruttore e per chi apre qualcosa", () => {
    render(
      <>
        <Button icon={IconEye} label="Mostra password" aria-pressed={false} />
        <Button aria-expanded={true}>Spostalo</Button>
      </>
    );
    expect(screen.getByRole("button", { name: "Mostra password" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Spostalo" })).toHaveAttribute("aria-expanded", "true");
  });
});

describe("buttonClasses", () => {
  // Due utilità dello stesso tipo sullo stesso elemento le decide l'ordine del CSS
  // compilato, non quello della stringa: jsdom non lo calcola, quindi qui si prova che
  // il conflitto non c'è. Ogni forma porta un raggio solo.
  const shapes: ButtonShape[] = ["pill", "block", "icon", "square"];
  const variants: ButtonVariant[] = ["primary", "secondary", "ghost", "danger", "warn"];
  it.each(shapes)("la forma %s ha un raggio solo, in ogni variante", (shape) => {
    for (const variant of variants) {
      const radii = buttonClasses(variant, shape)
        .split(/\s+/)
        .filter((c) => c.startsWith("rounded"));
      expect(radii, `${variant}/${shape}`).toHaveLength(1);
    }
  });

  it("il quadrato è un bersaglio da pollice, con il raggio dei pulsanti (spec T3 §3.2)", () => {
    const classes = buttonClasses("primary", "square").split(/\s+/);
    expect(classes).toContain("size-11");
    expect(classes).toContain("rounded-[10px]");
  });

  it("lo spento in volo si vede come lo spento vero, in ogni variante", () => {
    for (const variant of variants) {
      const classes = buttonClasses(variant).split(/\s+/);
      expect(classes, variant).toContain("disabled:opacity-40");
      expect(classes, variant).toContain("aria-disabled:opacity-40");
    }
  });
});

describe("IconToolbar", () => {
  it("raggruppa i pulsanti sotto un nome", () => {
    render(
      <IconToolbar label="Azioni sulla ricetta">
        <Button icon={IconPencil} label="Modifica" />
        <Button icon={IconTrash} label="Elimina" />
      </IconToolbar>
    );
    const toolbar = screen.getByRole("toolbar", { name: "Azioni sulla ricetta" });
    expect(toolbar.querySelectorAll("button")).toHaveLength(2);
  });
});
