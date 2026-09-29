import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { IngredientPicker } from "./IngredientPicker";
import type { Ingredient } from "../domain/types";

/** Un fetch che risponde in base al percorso: qui serve solo per registrare quale
 * rotta è stata chiamata, il corpo non conta. */
function stubRoutedFetch(route: (path: string, init?: RequestInit) => [unknown, number]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderWithClient(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const DETERSIVO: Ingredient = {
  id: "nf1",
  name: "detersivo per i piatti",
  display_name: "Detersivo per i piatti",
  category: "casa",
  kind: "non_food",
};

const LATTE: Ingredient = { id: "i1", name: "latte", display_name: "Latte", category: "latticini", kind: "food" };

describe("IngredientPicker", () => {
  it("chiede al server solo il cibo quando glielo si dice, e lo mette nella chiave", async () => {
    // due montaggi nello stesso QueryClient, stessa parola cercata: senza il kind
    // nella chiave il secondo leggerebbe la risposta del primo, e il filtro
    // diventerebbe una decorazione
    const chiamate: string[] = [];
    stubRoutedFetch((path) => {
      chiamate.push(path);
      // il percorso decide la risposta: solo la richiesta senza filtro include
      // la voce non alimentare, così una cache condivisa si vede sui *dati*
      // mostrati dai due selettori, non solo sull'URL partito
      if (path.includes("kind=food")) return [[], 200];
      return [[DETERSIVO], 200];
    });

    renderWithClient(
      <>
        <IngredientPicker label="Aggiungi in dispensa" failureNote="x" onPick={() => {}} />
        <IngredientPicker label="Contiene ingredienti" failureNote="x" kind="food" onPick={() => {}} />
      </>
    );
    const dispensa = screen.getByLabelText("Aggiungi in dispensa").closest("div")!;
    const ricette = screen.getByLabelText("Contiene ingredienti").closest("div")!;

    // la dispensa cerca e si lascia sistemare del tutto prima che il ricettario
    // cerchi la stessa parola: se la chiave è condivisa, il secondo montaggio
    // legge la voce non alimentare direttamente dalla cache del primo, senza
    // nemmeno aspettare una risposta di rete — è così che una corsa fra le due
    // richieste non maschera la collisione
    fireEvent.change(screen.getByLabelText("Aggiungi in dispensa"), { target: { value: "deter" } });
    await waitFor(() => {
      expect(within(dispensa).getByText("Detersivo per i piatti")).toBeDefined();
    });

    fireEvent.change(screen.getByLabelText("Contiene ingredienti"), { target: { value: "deter" } });

    // le URL: dicono che il parametro parte, cosa vera ma diversa da quella
    // che questo test deve difendere
    await waitFor(() => expect(chiamate.some((c) => c.includes("kind=food"))).toBe(true));
    expect(chiamate.some((c) => !c.includes("kind="))).toBe(true);

    // i dati: l'unica forma in cui una collisione di cache si rende visibile è
    // che i due selettori finiscano per mostrare lo stesso elenco. Ogni
    // `within` guarda solo il proprio contenitore, non lo `screen` globale,
    // perché entrambi i selettori rendono un elenco per la stessa parola
    await waitFor(() => {
      expect(within(ricette).queryByText("Detersivo per i piatti")).toBeNull();
    });

    // e la dispensa, che l'aveva già trovata, non deve perderla solo perché il
    // ricettario ha cercato la stessa parola un momento dopo: senza il `kind`
    // nella chiave la risposta (senza voce non alimentare) del ricettario
    // sovrascrive la voce condivisa in cache, e la dispensa la perde con lei —
    // esattamente la frase del brief e di CLAUDE.md, resa visibile
    expect(within(dispensa).getByText("Detersivo per i piatti")).toBeDefined();
  });

  it("ogni suggerimento è un'opzione della lista, senza voci d'elenco in mezzo", async () => {
    stubRoutedFetch(() => [[LATTE], 200]);
    renderWithClient(<IngredientPicker label="Contiene ingredienti" failureNote="x" onPick={() => {}} />);
    fireEvent.change(screen.getByLabelText("Contiene ingredienti"), { target: { value: "lat" } });
    // con un nome, come ARIA vuole per ogni listbox: quello del campo di cui è
    const listbox = await screen.findByRole("listbox", { name: "Suggerimenti: Contiene ingredienti" });
    // ARIA: i figli di un listbox sono opzioni, non `listitem` (dal giro di T3)
    expect(within(listbox).queryAllByRole("listitem")).toHaveLength(0);
    // il nome è l'ingrediente e basta, il reparto è una descrizione: prima si leggeva
    // «Lattelatticini»
    expect(within(listbox).getByRole("option", { name: "Latte" })).toHaveAccessibleDescription("latticini");
  });

  it("quando non trova niente offre di aggiungerlo, se chi lo usa sa crearlo", async () => {
    stubRoutedFetch(() => [[], 200]);
    const onCreate = vi.fn();
    renderWithClient(
      <IngredientPicker label="Aggiungi un ingrediente" failureNote="x" onPick={() => {}} onCreate={onCreate} />
    );
    fireEvent.change(screen.getByLabelText("Aggiungi un ingrediente"), { target: { value: "zz tre" } });
    fireEvent.click(await screen.findByRole("button", { name: "Aggiungi «zz tre»" }));
    expect(onCreate).toHaveBeenCalledWith("zz tre");
  });

  // S18 dall'altro lato: l'offerta di creare vale per il testo *cercato*, non per quello
  // scritto. Corretto «lattr» in «latte», per tutta l'attesa della ricerca la risposta
  // vuota in mano è ancora quella di «lattr»: offrire «Aggiungi «latte»» lì creerebbe
  // un doppione del latte che la ricerca sta per trovare.
  it("dopo una ricerca vuota, il testo corretto non si offre finché la sua ricerca non è finita", async () => {
    const cercati: string[] = [];
    stubRoutedFetch((path) => {
      cercati.push(new URL(path, "http://x").searchParams.get("q") ?? "");
      return [[], 200];
    });
    const onCreate = vi.fn();
    renderWithClient(
      <IngredientPicker label="Aggiungi un ingrediente" failureNote="x" onPick={() => {}} onCreate={onCreate} />
    );
    const campo = screen.getByLabelText("Aggiungi un ingrediente");
    fireEvent.change(campo, { target: { value: "lattr" } });
    await screen.findByRole("button", { name: "Aggiungi «lattr»" });

    fireEvent.change(campo, { target: { value: "latte" } });
    // subito dopo la correzione: nessuna offerta, né per il testo nuovo né per il vecchio
    expect(screen.queryByRole("button", { name: /^Aggiungi/ })).toBeNull();

    // finita la sua ricerca, vuota anche lei, l'offerta torna: per il testo cercato
    fireEvent.click(await screen.findByRole("button", { name: "Aggiungi «latte»" }));
    expect(cercati).toContain("latte");
    expect(onCreate).toHaveBeenCalledWith("latte");
  });

  it("senza onCreate, a ricerca vuota non offre niente: resta com'era", async () => {
    stubRoutedFetch(() => [[], 200]);
    renderWithClient(<IngredientPicker label="Contiene ingredienti" failureNote="x" onPick={() => {}} />);
    fireEvent.change(screen.getByLabelText("Contiene ingredienti"), { target: { value: "zz tre" } });
    await waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
    expect(screen.queryByRole("button", { name: /Aggiungi/ })).toBeNull();
  });

  // Senza `onCreate` una ricerca vuota non deve restare muta: chi usa il selettore
  // nomina la sua via d'uscita (la Dispensa: la lista), e la nota compare dove
  // comparirebbe l'offerta di creare — a ricerca finita e vuota, per il testo cercato.
  it("senza onCreate, a ricerca finita e vuota mostra la nota di chi lo usa", async () => {
    stubRoutedFetch(() => [[], 200]);
    renderWithClient(
      <IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} emptyNote="Scrivilo in lista." />
    );
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "zz tre" } });
    // mentre si scrive, prima che la ricerca sia finita, niente nota
    expect(screen.queryByText("Scrivilo in lista.")).toBeNull();
    expect(await screen.findByText("Scrivilo in lista.")).toBeDefined();
  });

  it("la nota del vuoto non compare se la ricerca trova qualcosa", async () => {
    stubRoutedFetch(() => [[LATTE], 200]);
    renderWithClient(
      <IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} emptyNote="Scrivilo in lista." />
    );
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "lat" } });
    await screen.findByRole("option", { name: "Latte" });
    expect(screen.queryByText("Scrivilo in lista.")).toBeNull();
  });

  it("con onCreate la nota del vuoto lascia il posto all'offerta di creare", async () => {
    stubRoutedFetch(() => [[], 200]);
    renderWithClient(
      <IngredientPicker
        label="Ingrediente"
        failureNote="x"
        onPick={() => {}}
        onCreate={() => {}}
        emptyNote="Scrivilo in lista."
      />
    );
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "zz tre" } });
    await screen.findByRole("button", { name: "Aggiungi «zz tre»" });
    expect(screen.queryByText("Scrivilo in lista.")).toBeNull();
  });

  it("parte dal testo che gli si passa, e cerca subito quello", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([{ id: "i1", name: "sale", display_name: "Sale", category: "condimenti", kind: "food" }]), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchSpy);
    renderWithClient(<IngredientPicker label="Quale ingrediente?" failureNote="Riprova." onPick={() => {}} initialTerm="sale" />);
    expect(screen.getByLabelText("Quale ingrediente?")).toHaveProperty("value", "sale");
    expect(await screen.findByRole("option", { name: "Sale" })).toBeDefined();
  });

  it("con autoFocus il campo prende il fuoco appena compare", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderWithClient(<IngredientPicker label="Quale ingrediente?" failureNote="Riprova." onPick={() => {}} autoFocus={true} />);
    expect(document.activeElement).toBe(screen.getByLabelText("Quale ingrediente?"));
  });

  // S6: in «Sistema la spesa» la creazione non può dipendere dal vuoto — «cera per
  // pavimenti» pescava sette suggerimenti, `Pera` in testa, e la porta spariva
  it("con createWhen «always» offre di aggiungere anche accanto ai suggerimenti", async () => {
    stubRoutedFetch(() => [[LATTE], 200]);
    const onCreate = vi.fn();
    renderWithClient(
      <IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} onCreate={onCreate} createWhen="always" />
    );
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "latte di capra" } });
    await screen.findByRole("option", { name: "Latte" });
    fireEvent.click(await screen.findByRole("button", { name: "Aggiungi «latte di capra»" }));
    expect(onCreate).toHaveBeenCalledWith("latte di capra");
  });

  it("con createWhen «always» offre di aggiungere anche se la ricerca non risponde", async () => {
    stubRoutedFetch(() => [{ detail: "giù" }, 500]);
    renderWithClient(
      <IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} onCreate={() => {}} createWhen="always" />
    );
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "cera" } });
    expect(await screen.findByRole("button", { name: "Aggiungi «cera»" })).toBeDefined();
  });

  it("di norma accanto ai suggerimenti non offre di aggiungere: resta com'era", async () => {
    stubRoutedFetch(() => [[LATTE], 200]);
    renderWithClient(
      <IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} onCreate={() => {}} />
    );
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "lat" } });
    await screen.findByRole("option", { name: "Latte" });
    expect(screen.queryByRole("button", { name: /Aggiungi/ })).toBeNull();
  });

  it("mentre la scelta di prima è in volo, «Aggiungi «…»» è spento ma tiene il fuoco, e non crea", async () => {
    stubRoutedFetch(() => [[], 200]);
    const onCreate = vi.fn();
    renderWithClient(
      <IngredientPicker
        label="Ingrediente"
        failureNote="x"
        onPick={() => {}}
        onCreate={onCreate}
        initialTerm="zz tre"
        disabled
      />
    );
    const aggiungi = await screen.findByRole("button", { name: "Aggiungi «zz tre»" });
    // `busy` e non `disabled` (Consegna 6a): il browser toglie il fuoco a un pulsante che
    // diventa `disabled`. Campo e suggerimenti restano spenti come prima (idea in
    // next-steps.md): cambia solo il pulsante
    expect(aggiungi).toHaveAttribute("aria-disabled", "true");
    expect(aggiungi.hasAttribute("disabled")).toBe(false);
    aggiungi.focus();
    expect(aggiungi).toHaveFocus();
    fireEvent.click(aggiungi);
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("il campo invita a cercare un ingrediente (spec T3 §4.7)", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderWithClient(<IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} />);
    expect(screen.getByLabelText("Ingrediente")).toHaveAttribute("placeholder", "Cerca un ingrediente");
  });
});
