import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusDot } from "./StatusDot";

// Le parole sono quelle di STATUS_LABELS (ruling del controller): un solo
// vocabolario per gli stessi tre stati, non uno diverso per la ricetta.
describe("StatusDot", () => {
  it.each([
    ["available", "disponibile", "bg-brand"],
    ["low", "quasi finito", "bg-low"],
    ["missing", "manca", "bg-finished"],
  ] as const)("%s si legge «%s» ed è %s", (availability, words, colour) => {
    render(<StatusDot availability={availability} />);
    const dot = screen.getByRole("img", { name: words });
    expect(dot.className).toContain(colour);
  });
});
