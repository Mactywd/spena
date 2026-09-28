import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusDot } from "./StatusDot";

// Il pallino non ha parole sue per i due stati che la dispensa già nomina: le prende da
// STATUS_LABELS, un vocabolario solo. Qui le parole della dispensa si cambiano per
// finta, e il pallino deve seguirle; se le avesse ribattute a mano resterebbe indietro.
// «manca» no: per una ricetta è la disponibilità, e la dispensa non ha quella parola.
vi.mock("../../features/pantry/statusLabels", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../features/pantry/statusLabels")>();
  return {
    ...original,
    STATUS_LABELS: { available: "Presente", low: "In esaurimento", finished: "Esaurito" },
  };
});

describe("StatusDot, le parole", () => {
  it.each([
    ["available", "presente"],
    ["low", "in esaurimento"],
    ["missing", "manca"],
  ] as const)("%s si legge «%s», dalle parole della dispensa", (availability, words) => {
    render(<StatusDot availability={availability} />);
    expect(screen.getByRole("img", { name: words })).toBeInTheDocument();
  });
});
