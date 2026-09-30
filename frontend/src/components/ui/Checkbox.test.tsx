import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Checkbox } from "./Checkbox";

describe("Checkbox", () => {
  it("dentro una label, un tocco sul quadrato intorno alla casella la spunta", async () => {
    const onChange = vi.fn();
    render(
      <label>
        <Checkbox aria-label="Includi basilico" checked={false} onChange={onChange} />
        Basilico
      </label>
    );
    const casella = screen.getByRole("checkbox", { name: "Includi basilico" });
    // il quadrato da 44 px è il genitore della casella: il tocco lì, non sul quadratino
    await userEvent.click(casella.parentElement!);
    expect(onChange).toHaveBeenCalledOnce();
  });

  it("è una casella vera, con i suoi attributi", () => {
    render(
      <label>
        <Checkbox aria-label="Di solito è secondario" defaultChecked aria-disabled="true" />
      </label>
    );
    const casella = screen.getByRole("checkbox", { name: "Di solito è secondario" });
    expect(casella).toBeChecked();
    expect(casella).toHaveAttribute("aria-disabled", "true");
  });
});
