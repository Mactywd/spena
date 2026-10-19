import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { NutrientTable } from "./NutrientTable";
import type { NutrientRow } from "../lib/nutrients";

const RIGHE: NutrientRow[] = [
  { key: "kcal", label: "Energia", unit: "kcal", main: true, value: 18 },
  { key: "fiber", label: "Fibre", unit: "g", main: true, value: null },
  { key: "vitamin_c", label: "Vitamina C", unit: "mg", main: false, value: 14 },
  { key: "iron", label: "Ferro", unit: "mg", main: false, value: 0.3 },
  { key: "zinc", label: "Zinco", unit: "mg", main: false, value: null },
];

describe("NutrientTable", () => {
  it("i principali ci sono sempre; uno che manca è «—», e per chi ascolta «non indicato»", () => {
    render(<NutrientTable caption="Per 100 g" rows={RIGHE} />);

    const tabella = screen.getByRole("table", { name: "Per 100 g" });
    expect(within(tabella).getByRole("rowheader", { name: "Energia" })).toBeInTheDocument();
    expect(within(tabella).getByRole("cell", { name: "18 kcal" })).toBeInTheDocument();
    const fibre = within(tabella).getByRole("rowheader", { name: "Fibre" }).closest("tr")!;
    expect(within(fibre).getByText("—")).toHaveAttribute("aria-hidden", "true");
    expect(within(fibre).getByText("non indicato nella tabella")).toBeInTheDocument();
  });

  it("gli altri stanno sotto «Vitamine e minerali», solo se hanno un valore", () => {
    render(<NutrientTable caption="Per 100 g" rows={RIGHE} />);

    expect(screen.getByText("Vitamine e minerali (2)")).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "Ferro", hidden: true })).toBeInTheDocument();
    expect(screen.queryByText("Zinco")).toBeNull();
  });

  it("senza altri niente «Vitamine e minerali»; una nota sta sotto il valore", () => {
    render(
      <NutrientTable
        caption="A porzione"
        rows={[{ key: "kcal", label: "Energia", unit: "kcal", main: true, value: 512, note: "su 3 righe di 4" }]}
      />
    );

    expect(screen.queryByText(/Vitamine e minerali/)).toBeNull();
    expect(screen.getByText("su 3 righe di 4")).toBeInTheDocument();
  });
});
