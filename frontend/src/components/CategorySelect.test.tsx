import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CategorySelect } from "./CategorySelect";

describe("CategorySelect", () => {
  it("di norma offre tutti i reparti, e i non alimentari a parte", () => {
    render(<CategorySelect value="altro" onChange={vi.fn()} />);
    const reparto = screen.getByRole("combobox", { name: "Reparto" }) as HTMLSelectElement;
    expect(reparto.options).toHaveLength(14);
    const gruppo = reparto.querySelector('optgroup[label="Non alimentari"]');
    expect(gruppo?.querySelector('option[value="casa"]')).not.toBeNull();
    expect(gruppo?.querySelector('option[value="igiene"]')).not.toBeNull();
  });

  it("`foodOnly` offre solo i reparti del cibo: una ricetta non può nominare un non alimentare", () => {
    render(<CategorySelect value="altro" onChange={vi.fn()} foodOnly />);
    const reparto = screen.getByRole("combobox", { name: "Reparto" }) as HTMLSelectElement;
    expect(reparto.options).toHaveLength(12);
    expect(reparto.querySelector("optgroup")).toBeNull();
    expect(within(reparto).queryByRole("option", { name: "Casa" })).toBeNull();
  });

  it("le voci si leggono con la maiuscola, e il valore resta quello del backend", async () => {
    const onChange = vi.fn();
    render(<CategorySelect value="altro" onChange={onChange} />);
    const reparto = screen.getByRole("combobox", { name: "Reparto" });
    expect(within(reparto).getByRole("option", { name: "Latticini" })).toHaveValue("latticini");
    await userEvent.selectOptions(reparto, "latticini");
    expect(onChange).toHaveBeenCalledWith("latticini");
  });

  it("l'etichetta in vista resta «Reparto», e il nome accessibile può dire per quale riga", () => {
    render(
      <CategorySelect value="carne" onChange={vi.fn()} accessibleLabel="Reparto per «speck»" />
    );
    expect(screen.getByRole("combobox", { name: "Reparto per «speck»" })).toHaveValue("carne");
    expect(screen.getByText("Reparto")).toBeInTheDocument();
  });
});
