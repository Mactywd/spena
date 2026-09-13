import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DecidedTermRow } from "./DecidedTermRow";
import type { ImportTerm } from "../../domain/types";

function term(overrides: Partial<ImportTerm> = {}): ImportTerm {
  return {
    id: "t1",
    display_name: "Rigatoni",
    occurrences: 3,
    suggestion: null,
    waiting_titles: [],
    decided_by: "ai",
    decided_action: "map",
    decided_name: "pasta",
    ...overrides,
  };
}

describe("DecidedTermRow", () => {
  it("dice a cosa è stato agganciato", () => {
    render(<DecidedTermRow term={term()} pending={false} onUndo={vi.fn()} />);
    expect(screen.getByText("Rigatoni")).toBeInTheDocument();
    expect(screen.getByText(/pasta/)).toBeInTheDocument();
  });

  it("dice quando è stato ignorato, senza nominare un ingrediente", () => {
    render(
      <DecidedTermRow
        term={term({ display_name: "Acqua", decided_action: "ignored", decided_name: null })}
        pending={false}
        onUndo={vi.fn()}
      />
    );
    expect(screen.getByText(/ignorato/i)).toBeInTheDocument();
  });

  it("il pulsante di annullamento nomina il termine", async () => {
    // una riga per termine: senza il nome, chi usa uno screen reader sente N
    // pulsanti «Annulla» identici e non sa quale sta premendo
    const onUndo = vi.fn();
    render(<DecidedTermRow term={term()} pending={false} onUndo={onUndo} />);
    await userEvent.click(
      screen.getByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    );
    expect(onUndo).toHaveBeenCalledOnce();
  });

  it("mentre una decisione è in corso il pulsante è disabilitato", () => {
    render(<DecidedTermRow term={term()} pending={true} onUndo={vi.fn()} />);
    expect(
      screen.getByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    ).toBeDisabled();
  });
});
