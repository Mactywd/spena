import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { DailyColumns } from "./DailyColumns";
import type { DaySpend } from "./types";

/** Giorni consecutivi da `primo`, con i costi dati. */
function giorni(primo: string, costi: number[]): DaySpend[] {
  const [anno, mese, giorno] = primo.split("-").map(Number);
  return costi.map((cost_usd, i) => ({
    day: new Date(Date.UTC(anno, mese - 1, giorno + i)).toISOString().slice(0, 10),
    cost_usd,
  }));
}

const colonne = (container: HTMLElement) => Array.from(container.querySelectorAll("rect[data-day]"));
const numero = (elemento: Element, nome: string) => parseFloat(elemento.getAttribute(nome) ?? "NaN");

describe("DailyColumns", () => {
  it("una colonna per ogni giorno con una spesa, il più caro alto tutto, i giorni a zero senza colonna", () => {
    const { container } = render(<DailyColumns days={giorni("2026-10-01", [0.002, 0, 0.008, 0.004])} />);

    const trovate = colonne(container);
    expect(trovate.map((colonna) => colonna.getAttribute("data-day"))).toEqual([
      "2026-10-01",
      "2026-10-03",
      "2026-10-04",
    ]);
    expect(trovate.map((colonna) => numero(colonna, "height"))).toEqual([25, 100, 50]);
    expect(trovate.map((colonna) => numero(colonna, "y"))).toEqual([75, 0, 50]);
    for (const colonna of trovate) expect(colonna).toHaveClass("fill-brand");
  });

  it("una spesa minuscola accanto a una grossa resta visibile", () => {
    const { container } = render(<DailyColumns days={giorni("2026-10-01", [1, 0.0001])} />);

    expect(numero(colonne(container)[1], "height")).toBe(2);
  });

  it("fino a 62 giorni una colonna ha lo spazio accanto, oltre si toccano; con pochi giorni non si allarga", () => {
    const trenta = render(<DailyColumns days={giorni("2026-09-14", Array(30).fill(0.001))} />);
    expect(numero(colonne(trenta.container)[0], "width")).toBeCloseTo(0.8);
    expect(numero(colonne(trenta.container)[0], "x")).toBeCloseTo(0.1);
    trenta.unmount();

    const cento = render(<DailyColumns days={giorni("2026-07-06", Array(100).fill(0.001))} />);
    expect(numero(colonne(cento.container)[0], "width")).toBe(1);
    cento.unmount();

    // il primo del mese: una colonna sola, larga quanto una di quattordici, nel mezzo
    const uno = render(<DailyColumns days={giorni("2026-10-01", [0.001])} />);
    const sola = colonne(uno.container)[0];
    expect(numero(sola, "width")).toBeCloseTo(0.8 / 14);
    expect(numero(sola, "x") + numero(sola, "width") / 2).toBeCloseTo(0.5);
  });

  it("sopra il giorno più caro, sotto le date ai due capi", () => {
    render(<DailyColumns days={giorni("2026-10-01", [0.002, 0.021, 0.004])} />);

    expect(screen.getByText("Il giorno più caro: 2 ottobre, 0,021 $")).toBeInTheDocument();
    expect(screen.getByText("1 ott")).toBeInTheDocument();
    expect(screen.getByText("3 ott")).toBeInTheDocument();
  });

  it("un giorno solo ha una data sola", () => {
    render(<DailyColumns days={giorni("2026-10-01", [0.002])} />);

    expect(screen.getAllByText("1 ott")).toHaveLength(1);
  });

  it("per chi non vede: un'immagine col riassunto, e la tabella dei giorni con una spesa", () => {
    render(<DailyColumns days={giorni("2026-10-01", [0.002, 0, 0.021])} />);

    expect(
      screen.getByRole("img", {
        name: /^Costo per giorno, dall'1 al 3 ottobre\. Il giorno più caro: 3 ottobre, 0,021\s\$\.$/,
      })
    ).toBeInTheDocument();
    const tabella = screen.getByRole("table", { name: "I giorni con una spesa" });
    expect(
      within(tabella)
        .getAllByRole("row")
        .map((riga) => (riga.textContent ?? "").replace(/\u00a0/g, " "))
    ).toEqual(["1 ottobre0,002 $", "3 ottobre0,021 $"]);
  });
});
