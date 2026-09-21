import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MissingBudgetFilter } from "./MissingBudgetFilter";

describe("MissingBudgetFilter", () => {
  it("segna il gradino scelto e spiega a parole cosa si sta guardando", () => {
    render(<MissingBudgetFilter value={2} onChange={vi.fn()} />);

    expect(
      screen.getByRole("radio", { name: "Al massimo 2 ingredienti da comprare." })
    ).toBeChecked();
    // «+2» da solo non dice niente: è la riga sotto a dire cosa si sta guardando
    expect(screen.getByText("Al massimo 2 ingredienti da comprare.")).toBeVisible();
  });

  it("parte da «Tutte» quando non c'è soglia", () => {
    render(<MissingBudgetFilter value={null} onChange={vi.fn()} />);
    expect(screen.getByRole("radio", { name: "Tutto il ricettario." })).toBeChecked();
  });

  it("comunica la soglia scelta", async () => {
    const onChange = vi.fn();
    render(<MissingBudgetFilter value={null} onChange={onChange} />);

    await userEvent.click(
      screen.getByRole("radio", { name: "Al massimo 1 ingrediente da comprare." })
    );

    expect(onChange).toHaveBeenCalledWith(1);
  });

  it("«Ora» è zero, non l'assenza di soglia", async () => {
    // il caso che un `if (maxMissing)` sbaglierebbe in silenzio, da qui fino alla query
    const onChange = vi.fn();
    render(<MissingBudgetFilter value={null} onChange={onChange} />);

    await userEvent.click(
      screen.getByRole("radio", { name: "Solo quelle che puoi cucinare adesso." })
    );

    expect(onChange).toHaveBeenCalledWith(0);
  });

  it("«Tutte» torna a nessuna soglia", async () => {
    const onChange = vi.fn();
    render(<MissingBudgetFilter value={0} onChange={onChange} />);

    await userEvent.click(screen.getByRole("radio", { name: "Tutto il ricettario." }));

    expect(onChange).toHaveBeenCalledWith(null);
  });
});
