import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";

describe("ErrorState", () => {
  it("dice cosa non è andato e offre sempre «Riprova»", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Non sono riuscito a caricare la dispensa." onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Non sono riuscito a caricare la dispensa.");
    fireEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("mentre riprova il pulsante non si ripete, e tiene il fuoco", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="x" onRetry={onRetry} retrying />);
    const button = screen.getByRole("button", { name: "Riprovo…" });
    // `aria-disabled` e non `disabled` (Button, `busy`): chi ha premuto «Riprova» da
    // tastiera non deve ritrovarsi il fuoco sulla pagina
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button.hasAttribute("disabled")).toBe(false);
    fireEvent.click(button);
    expect(onRetry).not.toHaveBeenCalled();
  });
});

describe("EmptyState", () => {
  it("ha un titolo, una riga e un'azione", () => {
    render(<EmptyState title="Niente da sistemare" body="Spunta prima qualcosa in lista." action={<a href="/lista">Vai alla lista</a>} />);
    expect(screen.getByRole("heading", { name: "Niente da sistemare" })).toBeInTheDocument();
    expect(screen.getByText("Spunta prima qualcosa in lista.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Vai alla lista" })).toBeInTheDocument();
  });
});
