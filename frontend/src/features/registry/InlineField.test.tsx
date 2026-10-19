import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InlineField } from "./InlineField";

/** Il campo con un valore salvato vero: `onSave` lo cambia, come la scheda riletta. */
function Saved({ start = "Reggiano", fail = false }: { start?: string; fail?: boolean }) {
  const [value, setValue] = useState(start);
  return (
    <InlineField
      label="Nome"
      value={value}
      required
      onSave={async (next) => {
        if (fail) throw new Error("guasto");
        setValue(next);
      }}
    />
  );
}

describe("InlineField", () => {
  it("a riposo «Salva» è spento: non c'è niente da salvare", () => {
    render(<Saved />);
    expect(screen.getByRole("button", { name: "Salva nome" })).toBeDisabled();
  });

  it("in volo «Salva» tiene il fuoco, e il campo non si scrive ma resta raggiungibile", async () => {
    const onSave = vi.fn(() => new Promise<void>(() => {}));
    render(<InlineField label="Nome" value="Reggiano" onSave={onSave} />);
    const campo = screen.getByLabelText("Nome");
    await userEvent.type(campo, " 30 mesi");
    const salva = screen.getByRole("button", { name: "Salva nome" });
    salva.focus();
    await userEvent.keyboard("{Enter}");

    expect(onSave).toHaveBeenCalledWith("Reggiano 30 mesi");
    expect(salva).toHaveAttribute("aria-disabled", "true");
    expect(salva).not.toBeDisabled();
    expect(salva).toHaveFocus();
    expect(campo).toHaveAttribute("readonly");
    expect(campo).not.toBeDisabled();
  });

  // Dopo un salvataggio riuscito «Salva» si spegne perché invariato, con `disabled`, che
  // toglie il fuoco: il fuoco torna nel campo prima (pulizie del 2026-10-13)
  it("salvato, il fuoco torna nel campo, e «Salva» si spegne senza averlo", async () => {
    render(<Saved />);
    const campo = screen.getByLabelText("Nome");
    await userEvent.type(campo, " 30 mesi");
    const salva = screen.getByRole("button", { name: "Salva nome" });
    salva.focus();
    await userEvent.keyboard("{Enter}");

    await waitFor(() => expect(campo).toHaveFocus());
    expect(campo).toHaveValue("Reggiano 30 mesi");
    expect(salva).toBeDisabled();
  });

  it("fallito, il fuoco resta su «Salva» e l'errore si legge", async () => {
    render(<Saved fail />);
    await userEvent.type(screen.getByLabelText("Nome"), " 30 mesi");
    const salva = screen.getByRole("button", { name: "Salva nome" });
    salva.focus();
    await userEvent.keyboard("{Enter}");

    expect(
      await screen.findByText("Non sono riuscito a salvare. Quel che hai scritto è ancora qui: riprova.")
    ).toBeInTheDocument();
    expect(salva).toHaveFocus();
    expect(salva).not.toHaveAttribute("aria-disabled");
  });

  it("obbligatorio e vuoto, «Salva» dice perché, senza disabled nativo, e non salva", async () => {
    const onSave = vi.fn();
    render(<InlineField label="Nome" value="Reggiano" required onSave={onSave} />);
    await userEvent.clear(screen.getByLabelText("Nome"));
    const salva = screen.getByRole("button", { name: "Salva nome" });

    expect(salva).not.toBeDisabled();
    expect(salva).toHaveAttribute("aria-disabled", "true");
    expect(salva).toHaveAccessibleDescription("Il campo «Nome» non può restare vuoto.");
    await userEvent.click(salva);
    expect(onSave).not.toHaveBeenCalled();
  });
});
