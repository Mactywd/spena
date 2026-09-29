import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NewIngredientFields } from "./NewIngredientFields";

function renderFields(props: { initialName?: string; busy?: boolean } = {}) {
  const onSubmit = vi.fn();
  const onCancel = vi.fn();
  render(
    <NewIngredientFields
      initialName={props.initialName ?? "zucchine tonde di Nizza"}
      busy={props.busy ?? false}
      onSubmit={onSubmit}
      onCancel={onCancel}
    />
  );
  return { onSubmit, onCancel };
}

describe("NewIngredientFields", () => {
  it("chiede il nome generico con un'etichetta che si vede, e parte dal nome dato", () => {
    renderFields();
    const name = screen.getByLabelText("Come si chiama in generale?") as HTMLInputElement;
    expect(name).toHaveValue("zucchine tonde di Nizza");
    expect(name.labels![0]).not.toHaveClass("sr-only");
  });

  it("crea col nome corretto, senza spazi ai lati, e col reparto scelto", async () => {
    const { onSubmit } = renderFields();
    const name = screen.getByLabelText("Come si chiama in generale?");
    await userEvent.clear(name);
    await userEvent.type(name, "  zucchina  ");
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "verdura");
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    expect(onSubmit).toHaveBeenCalledWith({ name: "zucchina", category: "verdura" });
  });

  it("chi non sceglie il reparto ottiene «altro», e il non alimentare è offerto a parte", async () => {
    const { onSubmit } = renderFields({ initialName: "cera per pavimenti" });
    const reparto = screen.getByLabelText("Reparto") as HTMLSelectElement;
    expect(reparto.value).toBe("altro");
    expect(reparto.querySelector('optgroup[label="Non alimentari"] option[value="casa"]')).not.toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    expect(onSubmit).toHaveBeenCalledWith({ name: "cera per pavimenti", category: "altro" });
  });

  it("l'Invio nel nome crea, come il pulsante", async () => {
    const { onSubmit } = renderFields({ initialName: "zucchina" });
    await userEvent.type(screen.getByLabelText("Come si chiama in generale?"), "{Enter}");
    expect(onSubmit).toHaveBeenCalledWith({ name: "zucchina", category: "altro" });
  });

  it("senza nome non crea, e dice perché", async () => {
    const { onSubmit } = renderFields({ initialName: "   " });
    const create = screen.getByRole("button", { name: "Crea l'ingrediente" });
    expect(create).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Scrivi il nome per crearlo.")).toBeDefined();
    await userEvent.click(create);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("mentre crea, il pulsante si spegne ma resta dov'è il fuoco, e non crea due volte", async () => {
    const { onSubmit } = renderFields({ busy: true });
    const create = screen.getByRole("button", { name: "Crea l'ingrediente" });
    expect(create).toHaveAttribute("aria-disabled", "true");
    expect(create).not.toBeDisabled();
    await userEvent.click(create);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("«Annulla» torna indietro senza creare", async () => {
    const { onSubmit, onCancel } = renderFields();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
