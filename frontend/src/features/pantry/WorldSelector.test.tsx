import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { WorldSelector } from "./WorldSelector";

describe("WorldSelector", () => {
  it("tre pulsanti in un gruppo col suo nome, uno solo premuto", () => {
    render(<WorldSelector value="non_food" onChange={() => {}} />);
    const gruppo = screen.getByRole("group", { name: "Cosa mostrare" });
    const pulsanti = within(gruppo).getAllByRole("button");
    expect(pulsanti.map((pulsante) => pulsante.textContent)).toEqual(["Tutto", "Cibo", "Casa"]);
    expect(pulsanti.map((pulsante) => pulsante.getAttribute("aria-pressed"))).toEqual([
      "false",
      "false",
      "true",
    ]);
  });

  it("toccarne uno lo chiede a chi lo usa, col mondo di quel pulsante", () => {
    const onChange = vi.fn();
    render(<WorldSelector value="all" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Casa" }));
    fireEvent.click(screen.getByRole("button", { name: "Cibo" }));
    expect(onChange.mock.calls).toEqual([["non_food"], ["food"]]);
  });
});
