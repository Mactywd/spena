import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { PantryRow } from "./PantryRow";
import type { PantryItem } from "../../domain/types";

const BASE: PantryItem = {
  id: "p1", ingredient_id: "i1", product_id: "pr1", ingredient_name: "yogurt greco",
  ingredient_category: "latticini", product_name: "Total 0%", product_brand: "Fage",
  status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z",
  expires_on: null, expiry: null,
};

function renderRow(over: Partial<PantryItem> = {}, props: Partial<Parameters<typeof PantryRow>[0]> = {}) {
  const handlers = {
    onStatus: vi.fn(),
    onRemove: vi.fn(),
    onRestock: vi.fn(),
    onExpiry: vi.fn().mockResolvedValue(undefined),
    onRevealed: vi.fn(),
  };
  render(
    <MemoryRouter>
      <ul>
        <PantryRow item={{ ...BASE, ...over }} busy={false} failed={false} listed={false} reveal={false} {...handlers} {...props} />
      </ul>
    </MemoryRouter>
  );
  return handlers;
}

describe("PantryRow", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 28, 12, 0));
  });
  afterEach(() => vi.useRealTimers());

  it("il nome è l'ingrediente, e sotto c'è il prodotto: un aggancio sbagliato si vede", () => {
    renderRow();
    expect(screen.getByRole("link", { name: "yogurt greco" })).toBeDefined();
    expect(screen.getByText("Total 0%")).toBeDefined();
  });

  it("una voce senza prodotto dice «sfuso»", () => {
    renderRow({ product_id: null, product_name: null, product_brand: null });
    expect(screen.getByText("sfuso")).toBeDefined();
  });

  it("il nome porta alla scheda del prodotto se c'è, e ci porta da dispensa", () => {
    renderRow();
    expect(screen.getByRole("link", { name: "yogurt greco" }).getAttribute("href")).toBe(
      "/anagrafica/prodotto/pr1?da=dispensa"
    );
  });

  it("il nome di una voce sfusa porta alla scheda dell'ingrediente, e ci porta da dispensa", () => {
    renderRow({ product_id: null, product_name: null, product_brand: null });
    expect(screen.getByRole("link", { name: "yogurt greco" }).getAttribute("href")).toBe(
      "/anagrafica/ingrediente/i1?da=dispensa"
    );
  });

  it("le tacche mandano lo stato toccato, non una percentuale", () => {
    const { onStatus } = renderRow();
    fireEvent.click(screen.getByRole("radio", { name: "Quasi finito" }));
    expect(onStatus).toHaveBeenCalledWith("low");
  });

  it("la scadenza vicina si legge relativa", () => {
    renderRow({ expires_on: "2026-10-01", expiry: "soon" });
    expect(screen.getByRole("button", { name: "Scadenza di Total 0%: scade tra 3 gg" })).toBeDefined();
  });

  it("senza scadenza offre di scriverla, e il campo manda la data all'uscita", async () => {
    const { onExpiry } = renderRow();
    fireEvent.click(screen.getByRole("button", { name: "+ scadenza per Total 0%" }));
    const field = screen.getByLabelText("Scadenza di Total 0%");
    fireEvent.change(field, { target: { value: "2026-10-05" } });
    fireEvent.blur(field);
    expect(onExpiry).toHaveBeenCalledWith("2026-10-05");
  });

  it("una voce finita dice «Finito» e offre «In lista»", () => {
    const { onRestock } = renderRow({ status: "finished" });
    expect(screen.getByText("Finito")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "In lista" }));
    expect(onRestock).toHaveBeenCalled();
  });

  it("se è già in lista non offre di rimettercela", () => {
    renderRow({ status: "finished" }, { listed: true });
    expect(screen.queryByRole("button", { name: "In lista" })).toBeNull();
    expect(screen.getByText("Già in lista")).toBeDefined();
  });

  it("una voce non finita non offre «In lista»", () => {
    renderRow({ status: "low" });
    expect(screen.queryByRole("button", { name: "In lista" })).toBeNull();
  });

  it("la ✕ è di sola icona e nomina la voce", () => {
    const { onRemove } = renderRow();
    fireEvent.click(screen.getByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    expect(onRemove).toHaveBeenCalled();
  });

  it("mentre una scrittura è in volo i controlli sono spenti", () => {
    const { onStatus } = renderRow({ status: "finished" }, { busy: true });
    // le tacche con `aria-disabled` e non `disabled`: così il fuoco resta dove le
    // frecce l'hanno portato (StockGauge), e un tocco non manda comunque niente
    for (const name of ["Disponibile", "Quasi finito", "Finito"]) {
      expect(screen.getByRole("radio", { name })).toHaveAttribute("aria-disabled", "true");
    }
    fireEvent.click(screen.getByRole("radio", { name: "Disponibile" }));
    expect(onStatus).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "In lista" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Togli Total 0% dalla dispensa" }).hasAttribute("disabled")).toBe(true);
    // la scadenza come le tacche: dopo un Invio il fuoco torna qui mentre il
    // salvataggio è in volo, e un `disabled` lo buttava sul `body` (lo misura l'e2e)
    const expiry = screen.getByRole("button", { name: "+ scadenza per Total 0%" });
    expect(expiry.hasAttribute("disabled")).toBe(false);
    expect(expiry).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(expiry);
    expect(screen.queryByLabelText("Scadenza di Total 0%")).toBeNull();
  });

  it("una scrittura fallita lo dice nella riga", () => {
    renderRow({}, { failed: true });
    expect(screen.getByRole("alert").textContent).toContain("Riprova");
  });

  it("con reveal si porta in vista e lo dice", () => {
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(() => {});
    const { onRevealed } = renderRow({}, { reveal: true });
    expect(scroll).toHaveBeenCalled();
    expect(onRevealed).toHaveBeenCalled();
    scroll.mockRestore();
  });

  // Comportamenti della riga, non dello schermo, sulla scadenza: `commitExpiry` in
  // PantryRow.tsx. Quel che la PATCH vera porta al server lo prova PantryScreen.test.tsx.

  it("scrivere una data la manda al server, e solo all'uscita dal campo", async () => {
    // Un `input[type="date"]` fa scattare `change` a ogni segmento toccato, non una
    // volta alla fine: battendo «2026» sull'anno il campo passa per 0002, 0020, 0202.
    // Legata al `change`, la scrittura partiva sul primo di quei valori e chiudeva il
    // campo sotto le dita — una data dell'anno 2 salvata e la correzione impossibile
    // da portare a termine con la tastiera. Le battute qui sotto sono quella sequenza:
    // nessuna di loro deve scrivere niente.
    const { onExpiry } = renderRow();
    fireEvent.click(screen.getByRole("button", { name: "+ scadenza per Total 0%" }));
    const field = screen.getByLabelText("Scadenza di Total 0%");
    for (const battuta of ["0002-10-05", "0020-10-05", "0202-10-05", "2026-10-05"]) {
      fireEvent.change(field, { target: { value: battuta } });
    }

    // il campo è ancora lì, e non è partito niente: si può continuare a correggere
    expect(screen.getByLabelText("Scadenza di Total 0%")).toBeDefined();
    expect(onExpiry).not.toHaveBeenCalled();

    fireEvent.blur(field);
    expect(onExpiry).toHaveBeenCalledTimes(1);
    expect(onExpiry).toHaveBeenCalledWith("2026-10-05");
  });

  it("l'Invio salva senza dover toccare altrove", () => {
    const { onExpiry } = renderRow();
    fireEvent.click(screen.getByRole("button", { name: "+ scadenza per Total 0%" }));
    const field = screen.getByLabelText("Scadenza di Total 0%");
    fireEvent.change(field, { target: { value: "2026-10-05" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onExpiry).toHaveBeenCalledWith("2026-10-05");
  });

  it("Esc chiude il campo senza scrivere, e il fuoco torna al pulsante", () => {
    const { onExpiry } = renderRow({ expires_on: "2026-10-05", expiry: null });
    fireEvent.click(screen.getByRole("button", { name: /Scadenza di Total 0%/ }));
    const field = screen.getByLabelText("Scadenza di Total 0%");
    fireEvent.change(field, { target: { value: "2027-01-01" } });
    fireEvent.keyDown(field, { key: "Escape" });

    const button = screen.getByRole("button", { name: /Scadenza di Total 0%/ });
    expect(onExpiry).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(button);
  });

  it("dopo un Esc, il campo riaperto salva di nuovo all'uscita", () => {
    const { onExpiry } = renderRow();
    fireEvent.click(screen.getByRole("button", { name: "+ scadenza per Total 0%" }));
    fireEvent.keyDown(screen.getByLabelText("Scadenza di Total 0%"), { key: "Escape" });

    fireEvent.click(screen.getByRole("button", { name: "+ scadenza per Total 0%" }));
    const field = screen.getByLabelText("Scadenza di Total 0%");
    fireEvent.change(field, { target: { value: "2026-10-05" } });
    fireEvent.blur(field);
    expect(onExpiry).toHaveBeenCalledWith("2026-10-05");
  });

  it("dopo l'Invio il fuoco torna al pulsante della scadenza, non si perde nella pagina", () => {
    renderRow();
    fireEvent.click(screen.getByRole("button", { name: "+ scadenza per Total 0%" }));
    const field = screen.getByLabelText("Scadenza di Total 0%");
    field.focus();
    fireEvent.change(field, { target: { value: "2026-10-05" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "+ scadenza per Total 0%" }));
  });

  it("il prodotto e la scadenza stanno su due righe loro, senza il punto fra loro", () => {
    // Con il «·» sulla stessa riga, un nome di prodotto vero («Coca Cola Bottiglia
    // 330ml») andava a capo e lasciava il punto da solo all'inizio o alla fine di una
    // riga: su 49 voci della dispensa vera, a 375px, 39 righe spezzate così.
    renderRow({ expires_on: "2026-10-05", expiry: "soon" });
    const row = screen.getByRole("listitem");
    expect(row.textContent).not.toContain("·");
    const product = screen.getByText("Total 0%");
    const expiry = screen.getByRole("button", { name: /Scadenza di Total 0%/ });
    expect(product.contains(expiry)).toBe(false);
    expect(product.parentElement!.contains(expiry)).toBe(false);
  });

  it("uscire dal campo senza aver cambiato niente non scrive", () => {
    const { onExpiry } = renderRow();
    fireEvent.click(screen.getByRole("button", { name: "+ scadenza per Total 0%" }));
    fireEvent.blur(screen.getByLabelText("Scadenza di Total 0%"));

    // il campo si richiude (si torna al «+ scadenza»), e niente è partito
    expect(screen.getByRole("button", { name: "+ scadenza per Total 0%" })).toBeDefined();
    expect(onExpiry).not.toHaveBeenCalled();
  });

  it("svuotare il campo manda null, che vuol dire cancellala", () => {
    // e non `{}`: quello lo decide lo schermo (il backend rifiuta un corpo vuoto con
    // 400), qui la riga manda solo `null`
    const { onExpiry } = renderRow({ expires_on: "2026-09-28", expiry: null });
    fireEvent.click(screen.getByRole("button", { name: /Scadenza di Total 0%/ }));
    const field = screen.getByLabelText("Scadenza di Total 0%");
    fireEvent.change(field, { target: { value: "" } });
    fireEvent.blur(field);
    expect(onExpiry).toHaveBeenCalledWith(null);
  });

  it("una scrittura della scadenza rifiutata non lascia il campo bloccato: il guasto lo dice l'Alert della riga", async () => {
    // il rifiuto lo mostra `failed` (lo decide lo schermo, `markFailed` in
    // PantryScreen.tsx nell'`onError` della mutazione `expiry`): qui si
    // prova solo che `commitExpiry` non propaga l'errore e chiude comunque il campo,
    // rirenderizzando poi con `failed` a vero come farebbe lo schermo dopo l'`onError`
    const onExpiry = vi.fn().mockRejectedValue(new Error("no"));
    const { rerender } = render(
      <MemoryRouter>
        <ul>
          <PantryRow item={BASE} busy={false} failed={false} listed={false} reveal={false}
            onStatus={vi.fn()} onRemove={vi.fn()} onRestock={vi.fn()} onExpiry={onExpiry} onRevealed={vi.fn()} />
        </ul>
      </MemoryRouter>
    );
    fireEvent.click(screen.getByRole("button", { name: "+ scadenza per Total 0%" }));
    fireEvent.change(screen.getByLabelText("Scadenza di Total 0%"), { target: { value: "2026-10-05" } });
    fireEvent.blur(screen.getByLabelText("Scadenza di Total 0%"));

    await waitFor(() => expect(onExpiry).toHaveBeenCalledWith("2026-10-05"));
    // il campo si è richiuso: non è rimasto aperto in attesa di una risposta che non
    // arriverà mai a chiuderlo lei
    expect(screen.getByRole("button", { name: "+ scadenza per Total 0%" })).toBeDefined();

    rerender(
      <MemoryRouter>
        <ul>
          <PantryRow item={BASE} busy={false} failed={true} listed={false} reveal={false}
            onStatus={vi.fn()} onRemove={vi.fn()} onRestock={vi.fn()} onExpiry={onExpiry} onRevealed={vi.fn()} />
        </ul>
      </MemoryRouter>
    );
    expect(screen.getByRole("alert").textContent).toContain("Riprova");
  });
});
