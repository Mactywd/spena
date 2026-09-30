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
    decided_at: "2026-09-20T10:00:00Z",
    ...overrides,
  };
}

describe("DecidedTermRow", () => {
  it("dice a cosa è stato agganciato", () => {
    render(<DecidedTermRow term={term()} pending={false} onUndo={vi.fn()} />);
    expect(screen.getByText("Rigatoni")).toBeInTheDocument();
    expect(screen.getByText(/pasta/)).toBeInTheDocument();
  });

  it("dice «creato dall'import» quando il termine possiede l'ingrediente creato, «collegato» altrimenti", () => {
    const { rerender } = render(
      <DecidedTermRow
        term={term({ display_name: "Speck", decided_name: "speck", created_ingredient: true })}
        pending={false}
        onUndo={vi.fn()}
      />
    );
    // «dall'import» e non «da questa decisione»: il flag può essere passato a questo
    // termine dal creatore annullato, e la frase resta vera anche lì
    expect(screen.getByText("creato dall'import: speck")).toBeInTheDocument();

    rerender(
      <DecidedTermRow term={term({ created_ingredient: false })} pending={false} onUndo={vi.fn()} />
    );
    expect(screen.getByText("collegato a pasta")).toBeInTheDocument();

    // le decisioni di prima non lo sanno: la frase non promette niente in più
    rerender(
      <DecidedTermRow term={term({ created_ingredient: null })} pending={false} onUndo={vi.fn()} />
    );
    expect(screen.getByText("collegato a pasta")).toBeInTheDocument();
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

  it("mentre una decisione è in corso il pulsante si spegne tenendo il fuoco, e il tocco non annulla", async () => {
    const onUndo = vi.fn();
    render(<DecidedTermRow term={term()} pending={true} onUndo={onUndo} />);
    const annulla = screen.getByRole("button", { name: /annulla la decisione su «Rigatoni»/i });
    expect(annulla).toHaveAttribute("aria-disabled", "true");
    expect(annulla).not.toBeDisabled();
    await userEvent.click(annulla);
    expect(onUndo).not.toHaveBeenCalled();
  });

  it("davanti a un nome che comincia per «a» dice «ad»: «collegato ad astice»", () => {
    render(
      <DecidedTermRow
        term={term({ display_name: "Astice blu", decided_name: "astice", created_ingredient: false })}
        pending={false}
        onUndo={vi.fn()}
      />
    );
    expect(screen.getByText("collegato ad astice")).toBeInTheDocument();
  });

  it("dice chi ha deciso: «AI» per l'AI, «tu» per una decisione a mano", () => {
    // un elenco solo per le due (R11): senza l'etichetta, una decisione a mano
    // sbagliata si legge come un errore dell'AI, e viceversa
    const { unmount } = render(<DecidedTermRow term={term()} pending={false} onUndo={vi.fn()} />);
    expect(screen.getByTestId("decided-by")).toHaveTextContent("AI");
    expect(screen.getByText("deciso dall'AI")).toBeInTheDocument();
    unmount();

    render(
      <DecidedTermRow term={term({ decided_by: "human" })} pending={false} onUndo={vi.fn()} />
    );
    expect(screen.getByTestId("decided-by")).toHaveTextContent("tu");
    expect(screen.getByText("deciso da te")).toBeInTheDocument();
  });
});
