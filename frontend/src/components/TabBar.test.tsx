import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { TabBar } from "./TabBar";
import indexHtml from "../../index.html?raw";

/**
 * La barra delle schede sta in fondo a ogni schermo, ed è l'unico elemento fisso
 * dell'app: su iPhone, e di più con la PWA installata (`display: standalone`), lì
 * passa l'indicatore home. Starne sopra dipende da tre cose in tre file diversi,
 * e basta che ne manchi una perché l'intenzione resti scritta e non realizzata —
 * com'era: il meta viewport non aveva `viewport-fit=cover`, quindi
 * `env(safe-area-inset-bottom)` valeva 0 e il `paddingBottom` non faceva nulla.
 * Nessun test in jsdom può misurare il risultato, ma può tenere insieme gli anelli
 * della catena. Due su tre: il terzo è la dichiarazione di `--safe-bottom` in
 * src/index.css, che non si può leggere da qui perché il plugin di Tailwind
 * restituisce stringa vuota per un import `?raw` di un foglio di stile — misurato.
 * Entrambi gli anelli verificati la nominano, quindi togliendola il motivo per cui
 * esistono resta scritto qui.
 */
describe("la barra delle schede sopra l'indicatore home", () => {
  it("il meta viewport chiede viewport-fit=cover, senza cui env(safe-area-inset-*) è 0", () => {
    const meta = indexHtml.match(/<meta name="viewport" content="([^"]*)"/)?.[1];
    expect(meta).toContain("viewport-fit=cover");
  });

  it("la barra usa --safe-bottom come spazio in fondo", () => {
    render(
      <MemoryRouter>
        <TabBar />
      </MemoryRouter>
    );
    const nav = screen.getByRole("navigation");
    expect(nav.style.paddingBottom).toBe("var(--safe-bottom)");
  });
});
