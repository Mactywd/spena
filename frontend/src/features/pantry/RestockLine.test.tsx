import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { RestockLine } from "./RestockLine";
import type { PantryStatus } from "../../domain/types";

function renderLine(status: PantryStatus, { listed = false, busy = false } = {}) {
  const onRestock = vi.fn();
  const view = render(
    <RestockLine status={status} listed={listed} busy={busy} onRestock={onRestock} />
  );
  return { ...view, onRestock };
}

describe("RestockLine", () => {
  it("su una voce finita dice «Finito», in rosso, e «In lista» la rimette in lista", () => {
    const { onRestock } = renderLine("finished");
    expect(screen.getByText("Finito")).toHaveClass("text-finished");
    fireEvent.click(screen.getByRole("button", { name: "In lista" }));
    expect(onRestock).toHaveBeenCalledTimes(1);
  });

  it("su una voce quasi finita dice «Quasi finito», nel colore del giallo, e offre «In lista» (Mattia, 2026-10-09)", () => {
    const { onRestock } = renderLine("low");
    expect(screen.getByText("Quasi finito")).toHaveClass("text-low");
    fireEvent.click(screen.getByRole("button", { name: "In lista" }));
    expect(onRestock).toHaveBeenCalledTimes(1);
  });

  it.each(["low", "finished"] as const)(
    "su una voce %s già in lista dice «Già in lista» e non offre di rimettercela",
    (status) => {
      renderLine(status, { listed: true });
      expect(screen.queryByRole("button", { name: "In lista" })).toBeNull();
      expect(screen.getByText("Già in lista")).toBeDefined();
    }
  );

  it("su una voce disponibile non disegna niente", () => {
    const { container } = renderLine("available");
    expect(container.innerHTML).toBe("");
  });

  it("mentre una scrittura è in volo «In lista» è spento con aria-disabled, e il tocco non parte", () => {
    const { onRestock } = renderLine("low", { busy: true });
    const button = screen.getByRole("button", { name: "In lista" });
    // `busy` e non `disabled`: il fuoco resta sul pulsante (regola di `Button`)
    expect(button.hasAttribute("disabled")).toBe(false);
    expect(button).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(button);
    expect(onRestock).not.toHaveBeenCalled();
  });
});
