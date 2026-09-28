import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { StockGauge } from "./StockGauge";

describe("StockGauge", () => {
  it("è un gruppo di tre scelte con le parole degli stati", () => {
    render(<StockGauge status="available" onChange={() => {}} itemName="Latte" />);
    const group = screen.getByRole("radiogroup", { name: "Quanto resta di Latte" });
    const names = [...group.querySelectorAll("[role=radio]")].map((r) => r.getAttribute("aria-label"));
    expect(names).toEqual(["Finito", "Quasi finito", "Disponibile"]);
    expect(screen.getByRole("radio", { name: "Disponibile" })).toHaveAttribute("aria-checked", "true");
  });

  it.each([
    ["Finito", "finished"],
    ["Quasi finito", "low"],
    ["Disponibile", "available"],
  ] as const)("toccare «%s» manda %s", (name, status) => {
    const onChange = vi.fn();
    render(<StockGauge status={status === "available" ? "low" : "available"} onChange={onChange} itemName="Latte" />);
    fireEvent.click(screen.getByRole("radio", { name }));
    expect(onChange).toHaveBeenCalledWith(status);
  });

  it("toccare lo stato che c'è già non manda niente", () => {
    const onChange = vi.fn();
    render(<StockGauge status="low" onChange={onChange} itemName="Latte" />);
    fireEvent.click(screen.getByRole("radio", { name: "Quasi finito" }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("il livello arriva fino alla tacca toccata: quasi finito accende due tacche", () => {
    render(<StockGauge status="low" onChange={() => {}} itemName="Latte" />);
    const lit = screen.getByRole("radiogroup").querySelectorAll("[data-lit=true]");
    expect(lit).toHaveLength(2);
  });

  it("le frecce spostano lo stato di una tacca, e il fuoco lo segue", () => {
    const onChange = vi.fn();
    render(<StockGauge status="low" onChange={onChange} itemName="Latte" />);
    const current = screen.getByRole("radio", { name: "Quasi finito" });
    expect(current).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("radio", { name: "Finito" })).toHaveAttribute("tabindex", "-1");
    fireEvent.keyDown(current, { key: "ArrowRight" });
    expect(onChange).toHaveBeenLastCalledWith("available");
    expect(screen.getByRole("radio", { name: "Disponibile" })).toHaveFocus();
    fireEvent.keyDown(current, { key: "ArrowLeft" });
    expect(onChange).toHaveBeenLastCalledWith("finished");
  });

  it("ogni tacca è un bersaglio da 44px", () => {
    render(<StockGauge status="low" onChange={() => {}} itemName="Latte" />);
    for (const radio of screen.getAllByRole("radio")) expect(radio.className).toContain("size-11");
  });
});
