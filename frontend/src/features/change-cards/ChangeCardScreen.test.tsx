import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { ChangeCardScreen } from "./ChangeCardScreen";
import { card, renderWith, stubFetch } from "./testkit";

afterEach(() => vi.unstubAllGlobals());

describe("ChangeCardScreen", () => {
  it("mostra il titolo della pagina e la scheda", async () => {
    stubFetch((url) => (url.includes("/pantry") ? [[], 200] : [card(), 200]));
    renderWith(<ChangeCardScreen />, "/pasti/cambi/c1");
    expect(screen.getByRole("heading", { level: 1, name: "Scheda dei cambi" })).toBeInTheDocument();
    expect(await screen.findByText("Cambi per la cena di martedì")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Pasti/ })).toHaveAttribute("href", "/pasti");
  });
});
