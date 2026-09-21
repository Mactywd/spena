import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExpiryChip } from "./ExpiryChip";

describe("ExpiryChip", () => {
  it("dice quando scade, al futuro", () => {
    render(<ExpiryChip expiresOn="2026-09-28" expiry="soon" />);
    expect(screen.getByText("Scade il 28/09/2026")).toBeInTheDocument();
  });

  it("al passato cambia tempo verbale, non genere", () => {
    // «scaduto» e «scaduta» costringerebbero a scegliere fra «Fage Total 0%» e
    // «passata di pomodoro», e una delle due sarebbe sempre sbagliata. L'imperfetto
    // non concorda con niente.
    render(<ExpiryChip expiresOn="2026-09-20" expiry="expired" />);
    expect(screen.getByText("Scadeva il 20/09/2026")).toBeInTheDocument();
  });

  it("senza verdetto la data si legge comunque, in tinta neutra", () => {
    render(<ExpiryChip expiresOn="2026-12-31" expiry={null} />);
    expect(screen.getByText("Scade il 31/12/2026")).toBeInTheDocument();
  });
});
