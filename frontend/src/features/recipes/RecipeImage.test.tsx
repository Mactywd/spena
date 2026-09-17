import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { RecipeImage } from "./RecipeImage";

describe("RecipeImage", () => {
  it("senza indirizzo non rende niente, non un riquadro vuoto", () => {
    const { container } = render(<RecipeImage url={null} alt="Carbonara" />);
    expect(container.firstChild).toBeNull();
  });

  it("mostra la foto con il titolo come testo alternativo", () => {
    render(<RecipeImage url="https://esempio.invalid/foto.jpg" alt="Carbonara" />);
    const foto = screen.getByRole("img", { name: "Carbonara" });
    expect(foto.getAttribute("src")).toBe("https://esempio.invalid/foto.jpg");
    // duecento schede su un telefono sono duecento immagini, e arrivano dal
    // server di origine
    expect(foto.getAttribute("loading")).toBe("lazy");
  });

  it("una foto che non carica sparisce invece di lasciare un buco", () => {
    // il difetto corretto in 6a2175b: l'immagine arriva dal server di origine e non
    // viene mai copiata (spec §6.3), quindi un 404 è il caso normale
    const { container } = render(<RecipeImage url="https://esempio.invalid/rotta.jpg" alt="Carbonara" />);
    fireEvent.error(screen.getByRole("img", { name: "Carbonara" }));
    expect(container.firstChild).toBeNull();
  });

  it("cambiando ricetta la foto nuova ha una possibilità: il guasto non si eredita", () => {
    // le schede dell'elenco hanno ognuna la sua chiave React, ma lo schermo della
    // ricetta non è chiavato per id: passando da una ricetta all'altra il
    // componente non si smonta, e un `failed` che non si azzera nasconderebbe
    // per sempre la foto buona della seconda
    const { container, rerender } = render(
      <RecipeImage url="https://esempio.invalid/rotta.jpg" alt="Carbonara" />
    );
    fireEvent.error(screen.getByRole("img", { name: "Carbonara" }));
    expect(container.firstChild).toBeNull();

    rerender(<RecipeImage url="https://esempio.invalid/buona.jpg" alt="Amatriciana" />);

    const foto = screen.getByRole("img", { name: "Amatriciana" });
    expect(foto.getAttribute("src")).toBe("https://esempio.invalid/buona.jpg");
  });
});
