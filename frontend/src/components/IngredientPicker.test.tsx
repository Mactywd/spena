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
});
