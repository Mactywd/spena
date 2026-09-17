import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { BackLink } from "./BackLink";

describe("BackLink", () => {
  it("porta a una destinazione dichiarata, non alla cronologia", () => {
    render(
      <MemoryRouter>
        <BackLink to="/ricette" label="Ricette" />
      </MemoryRouter>
    );
    expect(screen.getByRole("link", { name: "Ricette" }).getAttribute("href")).toBe("/ricette");
  });

  it("il segno di minore non entra nel nome del collegamento", () => {
    const { container } = render(
      <MemoryRouter>
        <BackLink to="/lista" label="Lista" />
      </MemoryRouter>
    );
    // il nome accessibile è «Lista»: se il chevron non fosse nascosto, chi legge
    // con la voce sentirebbe un carattere che non si pronuncia
    expect(screen.getByRole("link", { name: "Lista" })).toBeDefined();
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });
});
