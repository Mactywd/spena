import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Button } from "./Button";
import { buttonClasses, type ButtonShape, type ButtonVariant } from "./buttonClasses";
import { IconToolbar } from "./IconToolbar";
import { IconPencil, IconTrash } from "./icons";

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

  // La guardia di TypeScript che il vincolo globale chiede: un pulsante di sola
  // icona senza `label` non deve compilare, perché per uno screen reader non ha
  // nome. Se la riga sotto smette di dare errore, la regola si è rotta.
  it("compila solo se l'unione icona+etichetta è rispettata (vedi riga @ts-expect-error sopra)", () => {
    // @ts-expect-error icona sola senza `label` non deve compilare
    render(<Button icon={IconTrash} />);
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
