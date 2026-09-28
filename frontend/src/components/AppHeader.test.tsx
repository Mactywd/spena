import { afterEach, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { AppHeader } from "./AppHeader";

function renderHeader() {
  return render(
    <MemoryRouter>
      <AppHeader />
    </MemoryRouter>
  );
}

/** Un bottone che torna indietro nella cronologia: simula avanti/indietro del
 * browser, che cambia l'indirizzo senza passare da un `Link` dentro l'header. */
function IndietroButton() {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate(-1)}>
      torna indietro
    </button>
  );
}

function renderHeaderConCronologia() {
  return render(
    <MemoryRouter initialEntries={["/anagrafica", "/dispensa"]} initialIndex={1}>
      <AppHeader />
      <IndietroButton />
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

  it("porta il cesto, lo stesso segno dell'icona sul telefono", () => {
    renderHeader(); // l'aiutante che il file usa già per montare l'intestazione
    expect(screen.getByRole("banner").querySelector("svg[data-mark='cesto']")).not.toBeNull();
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

  it("un avanti/indietro del browser mentre il menu è aperto lo chiude", async () => {
    // il tocco su una voce chiude già da sé (test sopra): qui l'indirizzo cambia da
    // fuori, come lo fa avanti/indietro del browser, senza passare da un `Link`
    // dentro il pannello — quel percorso non chiudeva niente
    renderHeaderConCronologia();
    await userEvent.click(screen.getByRole("button", { name: "Apri il menu" }));
    expect(screen.getByRole("dialog", { name: "Menu" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "torna indietro" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  describe("lo scorrimento della pagina sotto il pannello", () => {
    // un valore di partenza non vuoto: il pannello deve rimettere quello che c'era, non
    // una stringa vuota scelta da lui
    afterEach(() => {
      document.body.style.overflow = "";
    });

    it("aperto il pannello la pagina non scorre, e chiuso torna com'era", async () => {
      document.body.style.overflow = "clip";
      renderHeader();

      await userEvent.click(screen.getByRole("button", { name: "Apri il menu" }));
      expect(document.body.style.overflow).toBe("hidden");

      await userEvent.keyboard("{Escape}");
      expect(document.body.style.overflow).toBe("clip");
    });

    it("torna com'era anche quando il pannello si chiude per un cambio di pagina", async () => {
      renderHeaderConCronologia();
      await userEvent.click(screen.getByRole("button", { name: "Apri il menu" }));
      expect(document.body.style.overflow).toBe("hidden");

      await userEvent.click(screen.getByRole("button", { name: "torna indietro" }));

      expect(document.body.style.overflow).toBe("");
    });

    it("torna com'era se l'intestazione sparisce col pannello aperto", async () => {
      document.body.style.overflow = "auto";
      const { unmount } = renderHeader();
      await userEvent.click(screen.getByRole("button", { name: "Apri il menu" }));
      expect(document.body.style.overflow).toBe("hidden");

      unmount();

      expect(document.body.style.overflow).toBe("auto");
    });
  });
});
