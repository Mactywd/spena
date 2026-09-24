import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CostMeter } from "./CostMeter";
import { CostPicker } from "./CostPicker";

describe("CostMeter", () => {
  it("dice il gradino a chi non vede il grigio", () => {
    render(<CostMeter cost={3} />);
    expect(screen.getByRole("img", { name: "Costo 3 su 5" })).toBeInTheDocument();
  });

  it("disegna sempre cinque €, pieni fino al gradino", () => {
    const { container } = render(<CostMeter cost={2} />);
    const segni = container.querySelectorAll("[data-cost-step]");
    expect(segni).toHaveLength(5);
    expect([...segni].map((s) => s.getAttribute("data-on"))).toEqual([
      "true", "true", "false", "false", "false",
    ]);
  });

  it("senza costo non disegna niente: non è una ricetta da uno", () => {
    const { container } = render(<CostMeter cost={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("CostPicker", () => {
  it("toccare un € sceglie quel gradino", async () => {
    const onChange = vi.fn();
    render(<CostPicker value={null} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Costo 3 su 5" }));
    expect(onChange).toHaveBeenCalledWith(3);
  });

  it("ritoccare quello scelto toglie il costo", async () => {
    const onChange = vi.fn();
    render(<CostPicker value={4} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Costo 4 su 5" }));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("dichiara quale gradino è scelto", () => {
    render(<CostPicker value={2} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Costo 2 su 5" })).toHaveAttribute(
      "aria-pressed", "true"
    );
    expect(screen.getByRole("button", { name: "Costo 3 su 5" })).toHaveAttribute(
      "aria-pressed", "false"
    );
  });

  it("spento, non accetta tocchi", async () => {
    const onChange = vi.fn();
    render(<CostPicker value={null} onChange={onChange} disabled />);
    await userEvent.click(screen.getByRole("button", { name: "Costo 1 su 5" }));
    expect(onChange).not.toHaveBeenCalled();
  });
});
