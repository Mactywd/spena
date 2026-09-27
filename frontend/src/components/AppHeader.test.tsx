import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("il ☰ apre un dialogo con l'indice, e ogni voce porta al suo posto", async () => {
    renderHeader();
    const apri = screen.getByRole("button", { name: "Apri il menu" });
    expect(apri).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(apri);

    const menu = screen.getByRole("dialog", { name: "Menu" });
    expect(apri).toHaveAttribute("aria-expanded", "true");
    expect(within(menu).getByRole("link", { name: "Sistema la spesa" })).toHaveAttribute("href", "/sistema");
    expect(within(menu).getByRole("link", { name: "Ingredienti da abbinare" })).toHaveAttribute(
      "href", "/ricette/importa"
    );
    expect(within(menu).getByRole("link", { name: "Anagrafica" })).toHaveAttribute("href", "/anagrafica");
  });

  it("aperto, il fuoco entra nel pannello; Esc lo chiude e il fuoco torna al ☰", async () => {
    renderHeader();
    const apri = screen.getByRole("button", { name: "Apri il menu" });

    await userEvent.click(apri);
    expect(screen.getByRole("button", { name: "Chiudi il menu" })).toHaveFocus();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(apri).toHaveFocus();
  });

  it("il fuoco resta dentro: dopo l'ultima voce si torna alla prima, e al contrario", async () => {
    renderHeader();
    await userEvent.click(screen.getByRole("button", { name: "Apri il menu" }));
    const ultima = screen.getByRole("link", { name: "Anagrafica" });
    const prima = screen.getByRole("button", { name: "Chiudi il menu" });

    ultima.focus();
    await userEvent.tab();
    expect(prima).toHaveFocus();

    await userEvent.tab({ shift: true });
    expect(ultima).toHaveFocus();
  });

  it("il tocco fuori dal pannello lo chiude, e il fuoco torna al ☰", async () => {
    renderHeader();
    const apri = screen.getByRole("button", { name: "Apri il menu" });
    await userEvent.click(apri);

    // il velo è in un portale su document.body (F4), non dentro `container`
    await userEvent.click(document.body.querySelector("[data-menu-backdrop]")!);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(apri).toHaveFocus();
  });

  it("scelta una voce, il pannello si chiude", async () => {
    renderHeader();
    await userEvent.click(screen.getByRole("button", { name: "Apri il menu" }));

    await userEvent.click(screen.getByRole("link", { name: "Anagrafica" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
