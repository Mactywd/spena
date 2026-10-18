import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AnchorField } from "./AnchorField";
import { AMOUNT_EMPTY, AMOUNT_NOT_A_NUMBER } from "./anchorAmount";

const FUORI_SCALA =
  "Così la ricetta cambierebbe più di 50 volte: scrivi un numero fra 6 g e 15000 g.";

function renderField(props: Partial<Parameters<typeof AnchorField>[0]> = {}) {
  const onSubmit = props.onSubmit ?? vi.fn().mockResolvedValue(null);
  const onCancel = props.onCancel ?? vi.fn();
  render(
    <AnchorField
      unit={props.unit === undefined ? "g" : props.unit}
      initial={props.initial ?? ""}
      onSubmit={onSubmit}
      onCancel={onCancel}
    />
  );
  return {
    onSubmit,
    onCancel,
    campo: screen.getByRole("textbox", { name: "Quanto ne fai?" }),
    riscala: screen.getByRole("button", { name: "Riscala" }),
  };
}

describe("AnchorField", () => {
  it("si apre col fuoco nella casella, la tastiera dei numeri, e l'unità della riga accanto", () => {
    const { campo } = renderField();
    expect(campo).toHaveFocus();
    expect(campo).toHaveAttribute("inputmode", "decimal");
    expect(campo).toHaveAccessibleDescription("g");
    expect(screen.getByText("g")).toBeInTheDocument();
  });

  it("un numero nudo non ha un'unità accanto", () => {
    const { campo } = renderField({ unit: null });
    expect(campo).not.toHaveAttribute("aria-describedby");
  });

  it("vuoto o non un numero, «Riscala» dice perché e non manda niente", async () => {
    const { campo, riscala, onSubmit } = renderField();
    expect(riscala).toHaveAttribute("aria-disabled", "true");
    expect(riscala).toHaveAccessibleDescription(AMOUNT_EMPTY);

    await userEvent.type(campo, "tanta");
    expect(riscala).toHaveAccessibleDescription(AMOUNT_NOT_A_NUMBER);
    await userEvent.click(riscala);
    await userEvent.type(campo, "{Enter}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("la virgola parte come punto", async () => {
    const { campo, riscala, onSubmit } = renderField();
    await userEvent.type(campo, "150,5");
    expect(riscala).not.toHaveAttribute("aria-disabled");
    await userEvent.click(riscala);
    expect(onSubmit).toHaveBeenCalledWith("150.5");
  });

  it("il perché del server resta sotto la casella, col numero scritto, e scrivendo se ne va", async () => {
    const onSubmit = vi.fn().mockResolvedValue(FUORI_SCALA);
    const { campo, riscala } = renderField({ onSubmit });
    await userEvent.type(campo, "99999");
    await userEvent.click(riscala);

    expect(await screen.findByRole("alert")).toHaveTextContent(FUORI_SCALA);
    expect(campo).toHaveValue("99999");
    // si può correggere e riprovare subito
    expect(riscala).not.toHaveAttribute("aria-disabled");
    await userEvent.type(campo, "{Backspace}");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("«Annulla» chiude senza mandare niente", async () => {
    const { campo, onSubmit, onCancel } = renderField();
    await userEvent.type(campo, "80");
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("parte dalla dose già fissata, se c'è", () => {
    const { campo, riscala } = renderField({ initial: "112,5" });
    expect(campo).toHaveValue("112,5");
    expect(riscala).not.toHaveAttribute("aria-disabled");
  });

  it("in volo «Riscala» aspetta, e un secondo tocco non riparte", async () => {
    const onSubmit = vi.fn(() => new Promise<string | null>(() => {}));
    const { campo, riscala } = renderField({ onSubmit });
    await userEvent.type(campo, "150");
    await userEvent.click(riscala);
    await userEvent.click(riscala);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(riscala).toHaveAttribute("aria-disabled", "true");
  });
});
