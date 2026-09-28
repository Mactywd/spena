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

  // Spec §4.4: le frecce passano da una tacca all'altra. La prima freccia manda lo
  // stato, la riga diventa occupata, e con l'attributo `disabled` il browser toglieva
  // il fuoco alla tacca: la seconda freccia non andava più da nessuna parte.
  it("spenta, una freccia non manda niente e il fuoco resta sulla tacca", () => {
    const onChange = vi.fn();
    const { rerender } = render(<StockGauge status="low" onChange={onChange} itemName="Latte" />);
    fireEvent.keyDown(screen.getByRole("radio", { name: "Quasi finito" }), { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledTimes(1);
    const next = screen.getByRole("radio", { name: "Disponibile" });
    expect(next).toHaveFocus();

    // la scrittura è in volo
    rerender(<StockGauge status="low" onChange={onChange} itemName="Latte" disabled />);
    expect(next).toHaveFocus();
    expect(next).toHaveAttribute("aria-disabled", "true");
    expect(next).not.toHaveAttribute("disabled");
    fireEvent.keyDown(next, { key: "ArrowLeft" });
    expect(next).toHaveFocus();
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("spenta, un tocco non manda niente", () => {
    const onChange = vi.fn();
    render(<StockGauge status="low" onChange={onChange} itemName="Latte" disabled />);
    fireEvent.click(screen.getByRole("radio", { name: "Finito" }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("ogni tacca è un bersaglio da 44px", () => {
    render(<StockGauge status="low" onChange={() => {}} itemName="Latte" />);
    for (const radio of screen.getAllByRole("radio")) expect(radio.className).toContain("size-11");
  });
});
