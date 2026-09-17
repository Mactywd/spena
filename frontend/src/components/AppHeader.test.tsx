import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppHeader } from "./AppHeader";

function renderHeader() {
  return render(
    <MemoryRouter>
      <AppHeader />
    </MemoryRouter>
  );
}

describe("AppHeader", () => {
  it("porta il nome dell'app, e il nome riporta alla schermata iniziale", () => {
    renderHeader();
    const home = screen.getByRole("link", { name: "Spena" });
    expect(home.getAttribute("href")).toBe("/");
  });

  it("sta in un banner: chi naviga per landmark deve trovarlo", () => {
    renderHeader();
    expect(screen.getByRole("banner")).toBeDefined();
  });

  it("il segno non ha un nome suo: il link si chiama «Spena», una volta sola", () => {
    // stessa regola delle icone della TabBar: senza `aria-hidden` chi legge con la
    // voce sentirebbe due volte la stessa cosa
    const { container } = renderHeader();
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });
});
